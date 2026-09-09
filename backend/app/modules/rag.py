"""RAG local (Blueprint §51) — recuperação de conhecimento de domínio.

Base de conhecimento LOCAL (procedimentos, taxonomias, dicionários de campos,
políticas metodológicas). O RAG fornece conhecimento de domínio; NÃO substitui
os dados do caso (§51). Recuperação por TF-IDF em Python puro — sem modelo de
embeddings externo e sem rede (§47, zero exfiltration).
"""

from __future__ import annotations

import math
import re
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.core.db import connect


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


# Tokenização sobre texto já normalizado (sem acento, minúsculo).
_TOKEN = re.compile(r"[a-z0-9_]+")
_STOP = {_strip_accents(w) for w in {
    "de", "da", "do", "das", "dos", "a", "o", "e", "que", "um", "uma", "para",
    "com", "não", "nao", "em", "por", "os", "as", "no", "na", "ao", "à", "se",
    "the", "of", "and", "to", "is", "in",
}}

# Stemming leve de português: remove sufixos comuns de plural/derivação.
# Preserva um radical de ao menos 3 letras para não colapsar palavras curtas.
_SUFFIXES = ("coes", "cao", "oes", "mentos", "mento", "adores", "ador",
             "acao", "ando", "adas", "ados", "ada", "ado", "res", "es", "s")

# Expansão por sinônimos de DOMÍNIO (aplicada só à consulta, não ao corpus).
# Melhora o recall sem embeddings: "movimentado" recupera docs sobre "valor".
_SYNONYMS = {
    "movimentado": ["valor", "montante"], "movimentacao": ["valor", "montante"],
    "movimentar": ["valor", "montante"], "reais": ["valor", "montante"],
    "real": ["valor"], "montante": ["valor"], "gasto": ["valor"],
    "transferencia": ["transacao"], "transferencias": ["transacao"],
    "vinculo": ["relacao", "entidade"], "vinculos": ["relacao", "entidade"],
    "homonimo": ["entidade", "identidade"], "homonimos": ["entidade", "identidade"],
    "duplicidade": ["duplicata", "deduplicacao"], "faltante": ["ausencia", "missing"],
}


def _stem(t: str) -> str:
    for suf in _SUFFIXES:
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)]
    return t


def _tokens(text: str) -> list[str]:
    """Tokens do corpus: normaliza acento, remove stopwords, aplica stemming."""
    norm = _strip_accents(text).lower()
    out = []
    for t in _TOKEN.findall(norm):
        if len(t) > 2 and t not in _STOP:
            out.append(_stem(t))
    return out


def _query_tokens(query: str) -> list[str]:
    """Tokens da consulta: como o corpus + expansão por sinônimos de domínio."""
    norm = _strip_accents(query).lower()
    raw = [t for t in _TOKEN.findall(norm) if len(t) > 2 and t not in _STOP]
    expanded = list(raw)
    for t in raw:
        expanded.extend(_SYNONYMS.get(t, []))
    return [_stem(t) for t in expanded]


def seed_kb() -> int:
    """Carrega os documentos de backend/kb/*.md na base, se ainda vazia."""
    with connect() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM rag_docs").fetchone()["c"]
    if n > 0:
        return n
    kb_dir = config.BACKEND_ROOT / "kb"
    if not kb_dir.exists():
        return 0
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        for path in sorted(kb_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            title = text.splitlines()[0].lstrip("# ").strip() if text else path.stem
            conn.execute(
                "INSERT INTO rag_docs (doc_id, title, source, text, created_at) VALUES (?,?,?,?,?)",
                (uuid.uuid4().hex, title, path.name, text, now),
            )
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) c FROM rag_docs").fetchone()["c"]


def add_doc(title: str, source: str, text: str) -> str:
    doc_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            "INSERT INTO rag_docs (doc_id, title, source, text, created_at) VALUES (?,?,?,?,?)",
            (doc_id, title, source, text, datetime.now(timezone.utc).isoformat()),
        )
    return doc_id


def list_docs() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT doc_id, title, source FROM rag_docs ORDER BY title").fetchall()
    return [dict(r) for r in rows]


def _load_corpus() -> list[dict]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM rag_docs")]


def search(query: str, k: int = 3) -> list[dict]:
    """Recupera os k documentos mais relevantes por TF-IDF cosine."""
    corpus = _load_corpus()
    if not corpus:
        return []
    q_tokens = _query_tokens(query)
    if not q_tokens:
        return []
    # Termos para destacar o trecho: preservam acento para casar no texto original.
    snip_terms = [t.lower() for t in re.findall(r"[^\W_]+", query, re.UNICODE)
                  if len(t) > 2 and _strip_accents(t.lower()) not in _STOP]

    docs_tokens = [_tokens(d["text"]) for d in corpus]
    df: Counter[str] = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    n_docs = len(corpus)
    idf = {t: math.log((1 + n_docs) / (1 + df[t])) + 1 for t in df}

    def vec(tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        return {t: (tf[t] / len(tokens)) * idf.get(t, 0.0) for t in tf}

    qv = vec(q_tokens)
    results = []
    for d, toks in zip(corpus, docs_tokens):
        dv = vec(toks)
        dot = sum(qv.get(t, 0) * dv.get(t, 0) for t in qv)
        nq = math.sqrt(sum(v * v for v in qv.values()))
        nd = math.sqrt(sum(v * v for v in dv.values()))
        score = dot / (nq * nd) if nq and nd else 0.0
        if score > 0:
            results.append({
                "doc_id": d["doc_id"], "title": d["title"], "source": d["source"],
                "score": round(score, 4),
                "snippet": _snippet(d["text"], snip_terms or q_tokens),
            })
    results.sort(key=lambda r: -r["score"])
    return results[:k]


def _snippet(text: str, q_tokens: list[str], width: int = 220) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in q_tokens if low.find(t) >= 0), default=-1)
    if pos < 0:
        return text[:width].strip()
    start = max(0, pos - width // 3)
    return ("…" if start else "") + text[start:start + width].strip() + "…"

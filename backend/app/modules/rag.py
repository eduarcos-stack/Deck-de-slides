"""RAG local (Blueprint §51) — recuperação de conhecimento de domínio.

Base de conhecimento LOCAL (procedimentos, taxonomias, dicionários de campos,
políticas metodológicas). O RAG fornece conhecimento de domínio; NÃO substitui
os dados do caso (§51). Recuperação por TF-IDF em Python puro — sem modelo de
embeddings externo e sem rede (§47, zero exfiltration).
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.core.db import connect

# Cache de vetores de embedding por (endpoint, modelo, doc_id) — corpus pequeno.
_EMB_CACHE: dict = {}


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


def _embeddings_endpoint() -> str | None:
    return os.environ.get("TRACELM_EMBEDDINGS_ENDPOINT")


def _embed_texts(texts: list[str]) -> list[list[float]]:
    """POST OpenAI-compatible /v1/embeddings; devolve um vetor por texto.

    Isolado para ser testável (monkeypatch). Ollama e servidores llama.cpp
    expõem esse mesmo protocolo. Só chaves/textos do enclave próprio trafegam.
    """
    import json
    import urllib.request

    endpoint = _embeddings_endpoint()
    model = os.environ.get("TRACELM_EMBEDDINGS_MODEL", "nomic-embed-text")
    timeout = float(os.environ.get("TRACELM_EMBEDDINGS_TIMEOUT", "15"))
    req = urllib.request.Request(
        endpoint, data=json.dumps({"model": model, "input": texts}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (endpoint próprio)
        data = json.loads(resp.read().decode())
    return [row["embedding"] for row in data["data"]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _search_embeddings(query: str, corpus: list[dict], snip_terms: list[str],
                       k: int) -> list[dict]:
    """Busca semântica por embeddings (seam §50), com cache dos vetores dos docs."""
    endpoint = _embeddings_endpoint()
    model = os.environ.get("TRACELM_EMBEDDINGS_MODEL", "nomic-embed-text")
    qv = _embed_texts([query])[0]

    missing_texts, missing_idx, doc_vecs = [], [], [None] * len(corpus)
    for i, d in enumerate(corpus):
        cached = _EMB_CACHE.get((endpoint, model, d["doc_id"]))
        if cached is not None:
            doc_vecs[i] = cached
        else:
            missing_texts.append(d["text"])
            missing_idx.append(i)
    if missing_texts:
        for j, vec in zip(missing_idx, _embed_texts(missing_texts)):
            _EMB_CACHE[(endpoint, model, corpus[j]["doc_id"])] = vec
            doc_vecs[j] = vec

    results = []
    for d, dv in zip(corpus, doc_vecs):
        score = _cosine(qv, dv)
        if score > 0:
            results.append({
                "doc_id": d["doc_id"], "title": d["title"], "source": d["source"],
                "score": round(score, 4), "snippet": _snippet(d["text"], snip_terms),
            })
    results.sort(key=lambda r: -r["score"])
    return results[:k]


def search(query: str, k: int = 3) -> list[dict]:
    """Recupera os k documentos mais relevantes.

    Padrão: TF-IDF local (§51, sem rede). Se TRACELM_EMBEDDINGS_ENDPOINT estiver
    configurado (enclave próprio §50), usa embeddings; em qualquer falha, cai de
    volta no TF-IDF — nunca quebra.
    """
    corpus = _load_corpus()
    if not corpus:
        return []
    # Termos para destacar o trecho: preservam acento para casar no texto original.
    snip_terms = [t.lower() for t in re.findall(r"[^\W_]+", query, re.UNICODE)
                  if len(t) > 2 and _strip_accents(t.lower()) not in _STOP]
    if _embeddings_endpoint():
        try:
            return _search_embeddings(query, corpus, snip_terms, k)
        except Exception:  # noqa: BLE001 — fallback TF-IDF local, nunca quebra
            pass
    q_tokens = _query_tokens(query)
    if not q_tokens:
        return []

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

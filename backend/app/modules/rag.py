"""RAG local (Blueprint §51) — recuperação de conhecimento de domínio.

Base de conhecimento LOCAL (procedimentos, taxonomias, dicionários de campos,
políticas metodológicas). O RAG fornece conhecimento de domínio; NÃO substitui
os dados do caso (§51). Recuperação por TF-IDF em Python puro — sem modelo de
embeddings externo e sem rede (§47, zero exfiltration).
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.core.db import connect

_TOKEN = re.compile(r"[a-zA-ZáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ0-9_]+")
_STOP = {
    "de", "da", "do", "das", "dos", "a", "o", "e", "que", "um", "uma", "para",
    "com", "não", "nao", "em", "por", "os", "as", "no", "na", "ao", "à", "se",
    "the", "of", "and", "to", "is", "in",
}


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text) if t.lower() not in _STOP and len(t) > 2]


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
    q_tokens = _tokens(query)
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
                "score": round(score, 4), "snippet": _snippet(d["text"], q_tokens),
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

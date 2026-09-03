"""Integridade da trilha por hash-chain + selo HMAC (Blueprint §36).

Cada entrada de uma trilha append-only (Diário de Transformação, log de acesso)
recebe:
  - prev_hash  — o entry_hash da entrada anterior (encadeamento);
  - entry_hash — SHA-256 de (prev_hash + conteúdo canônico da entrada);
  - seal       — HMAC-SHA256(segredo, entry_hash).

O encadeamento torna reordenação e remoção detectáveis; o selo HMAC impede que
quem adultera a trilha recompute os hashes sem conhecer o segredo (§48). Assim,
"alterações posteriores na trilha tornam-se detectáveis" (§36).
"""

from __future__ import annotations

import hashlib
import hmac
import json

from app.core.security import get_signing_secret

GENESIS = "0" * 64  # prev_hash da primeira entrada de cada trilha


def _canonical(fields: dict) -> str:
    return json.dumps(fields, sort_keys=True, ensure_ascii=False, default=str)


def compute_entry_hash(prev_hash: str, fields: dict) -> str:
    payload = (prev_hash + "|" + _canonical(fields)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seal(entry_hash: str) -> str:
    return hmac.new(get_signing_secret(), entry_hash.encode("ascii"), hashlib.sha256).hexdigest()


def last_hash(conn, table: str) -> str:
    """entry_hash da última entrada da trilha (ou GENESIS se vazia)."""
    row = conn.execute(
        f"SELECT entry_hash FROM {table} ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    return row["entry_hash"] if row and row["entry_hash"] else GENESIS


def link(conn, table: str, fields: dict) -> dict:
    """Calcula prev_hash/entry_hash/seal para uma nova entrada da trilha."""
    prev = last_hash(conn, table)
    entry = compute_entry_hash(prev, fields)
    return {"prev_hash": prev, "entry_hash": entry, "seal": seal(entry)}


def verify_chain(conn, table: str, content_fields, order_by: str = "rowid") -> dict:
    """Recalcula a cadeia e valida encadeamento + selo (§36).

    content_fields: ordem/nome das colunas que compõem o conteúdo canônico.
    Retorna {ok, entries, broken_at, reason}.
    """
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
    prev = GENESIS
    for i, r in enumerate(rows):
        fields = {k: r[k] for k in content_fields}
        expected_hash = compute_entry_hash(prev, fields)
        if r["prev_hash"] != prev:
            return {"ok": False, "entries": len(rows), "broken_at": i,
                    "reason": "prev_hash não encadeia com a entrada anterior"}
        if r["entry_hash"] != expected_hash:
            return {"ok": False, "entries": len(rows), "broken_at": i,
                    "reason": "conteúdo alterado (entry_hash não confere)"}
        if r["seal"] != seal(r["entry_hash"]):
            return {"ok": False, "entries": len(rows), "broken_at": i,
                    "reason": "selo HMAC inválido"}
        prev = r["entry_hash"]
    return {"ok": True, "entries": len(rows), "broken_at": None, "reason": "trilha íntegra"}

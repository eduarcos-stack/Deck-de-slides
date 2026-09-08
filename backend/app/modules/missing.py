"""Módulo 4 — Missing Data Semantic Analyzer (Blueprint §15).

Detecta representações de ausência (NULL, "", N/A, NI, não informado, não consta,
0, -1, 999999, 01/01/1900) e pergunta: "o que esta representação significa nesta
fonte?". NUNCA assume equivalência automaticamente (P3) — apenas o que um humano
confirma passa a valer para os motores (ex.: Entity Resolution).

Sem a confirmação, o analyzer só SINALIZA candidatos. Com a confirmação, um
sentinela como "-1" ou "999999" no CPF passa a ser tratado como MISSING pela ER,
em vez de virar um valor conflitante que gera false split (limitação exposta
pelas métricas do §62-67).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.db import connect

# Representações candidatas a ausência (§15). São CANDIDATAS — não equivalências.
SENTINEL_CANDIDATES = {
    "", "n/a", "na", "ni", "não informado", "nao informado", "não consta",
    "nao consta", "null", "none", "-1", "999999", "0", "01/01/1900",
}

# Campos onde "0" NÃO é ausência (é valor legítimo) — evita sugerir sentinela indevida.
_ZERO_IS_VALUE = {"amount", "value", "valor"}


def _payloads(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    return [json.loads(r["original_payload"]) for r in rows]


def _is_candidate(field: str, value: str) -> bool:
    v = (value or "").strip().lower()
    if v == "":
        return True
    if v == "0" and field.lower() in _ZERO_IS_VALUE:
        return False  # zero é valor legítimo neste campo
    return v in SENTINEL_CANDIDATES


def analyze(dataset_id: str) -> dict:
    """Sinaliza, por campo, os valores candidatos a ausência e seus estados (§15)."""
    payloads = _payloads(dataset_id)
    confirmed = _confirmed_raw(dataset_id)  # {(field, value): semantic}
    columns = list(payloads[0].keys()) if payloads else []

    fields = []
    for col in columns:
        counts: dict[str, int] = {}
        for p in payloads:
            v = p.get(col)
            if v is not None and _is_candidate(col, v):
                key = "" if v.strip() == "" else v
                counts[key] = counts.get(key, 0) + 1
        if not counts:
            continue
        candidates = []
        for value, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            candidates.append({
                "value": value,
                "display": value if value != "" else "(vazio)",
                "count": n,
                "confirmed_semantic": confirmed.get((col, value)),
            })
        fields.append({
            "field": col,
            "candidates": candidates,
            "question": f"O que estas representações significam no campo '{col}' nesta fonte?",
        })

    return {
        "dataset_id": dataset_id,
        "fields": fields,
        "note": ("Representações CANDIDATAS a ausência. Nenhuma equivalência é "
                 "assumida automaticamente (§15, P3); confirme o significado por "
                 "campo para que os motores passem a usá-lo."),
    }


def confirm(dataset_id: str, field: str, value: str, semantic: str, actor: str) -> dict:
    """Registra a interpretação humana de uma representação (§15, P9)."""
    if semantic not in ("MISSING", "SENTINEL_ZERO", "LEGIT_VALUE", "UNKNOWN"):
        raise ValueError("semântica inválida")
    with connect() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO missing_semantics
               (dataset_id, field, value, semantic, decided_by, at)
               VALUES (?,?,?,?,?,?)""",
            (dataset_id, field, value, semantic, actor,
             datetime.now(timezone.utc).isoformat()),
        )
    return {"dataset_id": dataset_id, "field": field, "value": value,
            "semantic": semantic, "decided_by": actor}


def _confirmed_raw(dataset_id: str) -> dict[tuple[str, str], str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT field, value, semantic FROM missing_semantics WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return {(r["field"], r["value"]): r["semantic"] for r in rows}


def confirmed_missing(dataset_id: str) -> dict[str, set[str]]:
    """Mapa field -> conjunto de valores brutos confirmados como MISSING.

    Usado pela Entity Resolution para tratar sentinelas como ausência, não conflito.
    """
    out: dict[str, set[str]] = {}
    for (field, value), semantic in _confirmed_raw(dataset_id).items():
        if semantic == "MISSING":
            out.setdefault(field, set()).add(value)
    return out

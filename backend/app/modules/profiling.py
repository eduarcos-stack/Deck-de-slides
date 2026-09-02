"""Módulo 2 — Data Profiling (Blueprint §12, §13).

Diagnóstico automático e reproduzível de um dataset: estrutura, cardinalidade,
missingness (com sentinelas semânticas — §15), domínio, formatos, chaves
candidatas e duplicidade. NENHUMA transformação é executada nesta etapa (§13):
o profiling apenas descreve, não corrige.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter

from app.core.db import connect
from app.models.schemas import ColumnProfile, DatasetProfile

# Sentinelas de ausência semântica (Blueprint §15). Detectadas, NUNCA
# convertidas automaticamente em equivalência (Missing Data Semantic Analyzer).
MISSING_SENTINELS = {
    "",
    "n/a",
    "na",
    "ni",
    "não informado",
    "nao informado",
    "não consta",
    "nao consta",
    "null",
    "-1",
    "999999",
    "01/01/1900",
}

# Detectores de formato (Blueprint §12 — Formatos). Regex propositalmente
# permissivos: o objetivo é diagnosticar heterogeneidade, não validar.
_FORMAT_PATTERNS = {
    "cpf_formatted": re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$"),
    "cpf_digits": re.compile(r"^\d{11}$"),
    "cnpj_formatted": re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$"),
    "cnpj_digits": re.compile(r"^\d{14}$"),
    "phone_e164": re.compile(r"^\+55\d{10,11}$"),
    "phone_formatted": re.compile(r"^\(?\d{2}\)?\s?\d{4,5}-?\d{4}$"),
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "date_iso": re.compile(r"^\d{4}-\d{2}-\d{2}"),
    "date_br": re.compile(r"^\d{2}/\d{2}/\d{4}"),
    "datetime_offset": re.compile(r"\d{2}:\d{2}.*[+-]\d{2}:?\d{2}$"),
    "currency_brl": re.compile(r"^R\$\s?\d"),
}


def _detect_formats(values: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for v in values:
        for name, pattern in _FORMAT_PATTERNS.items():
            if pattern.match(v):
                counts[name] += 1
    return dict(counts)


def _load_records(dataset_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return [json.loads(r["original_payload"]) for r in rows]


def _infer_type(values: list[str]) -> str:
    if not values:
        return "empty"
    ints = sum(1 for v in values if re.fullmatch(r"-?\d+", v))
    floats = sum(1 for v in values if re.fullmatch(r"-?\d+[.,]\d+", v))
    dates = sum(1 for v in values if _FORMAT_PATTERNS["date_br"].match(v)
                or _FORMAT_PATTERNS["date_iso"].match(v))
    n = len(values)
    if ints == n:
        return "integer"
    if ints + floats == n:
        return "numeric"
    if dates == n:
        return "date"
    return "string"


def profile_dataset(dataset_id: str) -> DatasetProfile:
    """Produz o DATASET PROFILE (§13). Objeto somente-leitura."""
    records = _load_records(dataset_id)
    row_count = len(records)
    columns: list[str] = list(records[0].keys()) if records else []

    col_profiles: list[ColumnProfile] = []
    candidate_keys: list[str] = []

    for col in columns:
        raw_values = [rec.get(col) for rec in records]
        present = [v for v in raw_values if v is not None]
        null_count = sum(1 for v in raw_values if v is None)
        empty_count = sum(1 for v in present if v.strip() == "")
        non_empty = [v for v in present if v.strip() != ""]

        sentinels: Counter[str] = Counter()
        for v in present:
            if v.strip().lower() in MISSING_SENTINELS:
                sentinels[v.strip()] += 1

        value_counts = Counter(non_empty)
        unique_count = len(value_counts)
        top_values = value_counts.most_common(5)

        sortable = sorted(non_empty)
        min_v = sortable[0] if sortable else None
        max_v = sortable[-1] if sortable else None

        is_key = (
            unique_count == row_count
            and null_count == 0
            and empty_count == 0
            and row_count > 0
        )
        if is_key:
            candidate_keys.append(col)

        col_profiles.append(
            ColumnProfile(
                name=col,
                inferred_type=_infer_type(non_empty),
                non_null=len(present),
                null_count=null_count,
                empty_count=empty_count,
                unique_count=unique_count,
                top_values=[(str(k), c) for k, c in top_values],
                min_value=min_v,
                max_value=max_v,
                detected_formats=_detect_formats(non_empty),
                missing_sentinels=dict(sentinels),
                is_candidate_key=is_key,
            )
        )

    exact_dupes, near_pairs = _duplicate_stats(records)
    critical_missing = _critical_missing_rows(records, columns)

    notes: list[str] = []
    if not candidate_keys:
        notes.append(
            "Nenhuma chave candidata de coluna única. Definir unidade de registro "
            "antes de deduplicar (P5)."
        )
    multi_format_cols = [
        c.name for c in col_profiles if len(c.detected_formats) > 1
    ]
    if multi_format_cols:
        notes.append(
            "Heterogeneidade de formato detectada em: "
            + ", ".join(multi_format_cols)
            + ". Normalização recomendada (sem executar nesta etapa)."
        )

    return DatasetProfile(
        dataset_id=dataset_id,
        row_count=row_count,
        column_count=len(columns),
        encoding="utf-8",
        columns=col_profiles,
        candidate_keys=candidate_keys,
        exact_duplicate_rows=exact_dupes,
        near_duplicate_pairs=near_pairs,
        critical_missing_rows=critical_missing,
        notes=notes,
    )


def _duplicate_stats(records: list[dict]) -> tuple[int, int]:
    """Conta linhas idênticas e pares quase idênticos (§12 — Duplicidade)."""
    seen: Counter[str] = Counter()
    for rec in records:
        seen[json.dumps(rec, sort_keys=True, ensure_ascii=False)] += 1
    exact = sum(c - 1 for c in seen.values() if c > 1)

    # Pares quase idênticos: >= 80% dos campos iguais, mas não idênticos.
    near = 0
    n = len(records)
    cols = list(records[0].keys()) if records else []
    threshold = math.ceil(0.8 * len(cols)) if cols else 0
    for i in range(n):
        for j in range(i + 1, n):
            equal = sum(
                1 for c in cols if records[i].get(c) == records[j].get(c)
            )
            if threshold <= equal < len(cols):
                near += 1
    return exact, near


def _critical_missing_rows(records: list[dict], columns: list[str]) -> int:
    """Linhas com ausência em campo crítico (heurística: colunas de id/valor)."""
    critical = [
        c for c in columns
        if any(tok in c.lower() for tok in ("id", "cpf", "valor", "value", "event"))
    ]
    if not critical:
        return 0
    count = 0
    for rec in records:
        for c in critical:
            v = rec.get(c)
            if v is None or (isinstance(v, str) and v.strip().lower() in MISSING_SENTINELS):
                count += 1
                break
    return count

"""Módulo 6 — Deduplication Engine (Blueprint §20, §21).

O sistema não pergunta apenas "as linhas são iguais?". Pergunta primeiro:
"qual é a unidade de ocorrência?" (§20). A unidade de evento é escolhida
EXPLICITAMENTE pelo usuário (event_key), materializando P5 (Event Identity Is
Explicit) — não se deduplica sem antes definir o que é um evento.

Categorias (§20):
  EXACT_DUPLICATE          — linhas idênticas em todos os campos
  TECHNICAL_DUPLICATE      — mesma chave de evento; diferem só em campos não-core
  LEGITIMATE_REPEATED_EVENT— chaves de evento distintas, mas repetição legítima
  UNRESOLVED               — mesma chave, mas divergência em campo core (suspeito)

A análise é somente-leitura e produz um FINDING/relatório. A canonicalização
(consolidação) só ocorre por aprovação (§43) e NUNCA apaga o raw (P1): registra
uma transformação reversível e marca os registros não-canônicos no nível derivado.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from app.core.db import connect
from app.governance import provenance
from app.models.schemas import Transformation

# Campos considerados "não-core" para distinguir duplicata técnica de divergência
# real. Diferenças apenas nestes campos indicam reimportação/ruído de cadastro.
DEFAULT_NON_CORE = {"notes", "source_system", "device_id", "record_id"}


def _records(dataset_id: str) -> list[tuple[str, dict]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT record_id, original_payload FROM raw_records WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return [(r["record_id"], json.loads(r["original_payload"])) for r in rows]


def _classify_group(payloads: list[dict], non_core: set[str]) -> str:
    """Classifica um grupo com a MESMA chave de evento."""
    if len(payloads) == 1:
        return "UNIQUE"
    core_keys = [k for k in payloads[0].keys() if k not in non_core]
    first_full = json.dumps(payloads[0], sort_keys=True, ensure_ascii=False)
    all_identical = all(
        json.dumps(p, sort_keys=True, ensure_ascii=False) == first_full for p in payloads
    )
    if all_identical:
        return "EXACT_DUPLICATE"
    core_signature = {
        tuple((k, p.get(k)) for k in core_keys) for p in payloads
    }
    if len(core_signature) == 1:
        # campos core idênticos; divergem só em não-core -> duplicata técnica
        return "TECHNICAL_DUPLICATE"
    return "UNRESOLVED"


def analyze(dataset_id: str, event_key: str, non_core: set[str] | None = None) -> dict:
    """Analisa a duplicidade sob uma unidade de evento explícita (§20)."""
    non_core = non_core or DEFAULT_NON_CORE
    records = _records(dataset_id)
    if records and event_key not in records[0][1]:
        raise KeyError(f"Chave de evento inexistente: {event_key}")

    groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for record_id, payload in records:
        groups[payload.get(event_key, "∅")].append((record_id, payload))

    report_groups = []
    counts = defaultdict(int)
    canonical_events = 0
    for key, members in groups.items():
        payloads = [p for _, p in members]
        category = _classify_group(payloads, non_core)
        counts[category] += 1
        canonical_events += 1  # cada chave de evento distinta = 1 evento canônico
        if len(members) > 1:
            report_groups.append(
                {
                    "event_key_value": key,
                    "category": category,
                    "member_record_ids": [rid for rid, _ in members],
                    "size": len(members),
                }
            )

    return {
        "dataset_id": dataset_id,
        "event_key": event_key,
        "raw_rows": len(records),
        "distinct_event_keys": len(groups),
        "canonical_events_estimate": canonical_events,
        "category_counts": {k: v for k, v in counts.items()},
        "duplicate_groups": report_groups,
        "note": (
            "Análise somente-leitura. A redução de linhas brutas para eventos "
            "canônicos é uma estimativa sob a unidade de evento escolhida; "
            "consolidar exige aprovação (§43) e não apaga o raw (P1)."
        ),
    }


def canonicalize(
    dataset_id: str, event_key: str, *, approved_by: str, justification: str = ""
) -> dict:
    """Consolida grupos EXACT/TECHNICAL após aprovação humana (§43, P9).

    Não apaga registros brutos (P1). Registra a decisão como transformação
    reversível (§35) e marca no nível derivado quais registros são canônicos.
    """
    report = analyze(dataset_id, event_key)
    transformation_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)

    # Só EXACT/TECHNICAL são consolidáveis; UNRESOLVED e repetições legítimas não.
    consolidable = [
        g for g in report["duplicate_groups"]
        if g["category"] in ("EXACT_DUPLICATE", "TECHNICAL_DUPLICATE")
    ]
    consolidated = sum(len(g["member_record_ids"]) - 1 for g in consolidable)

    with connect() as conn:
        case_row = conn.execute(
            "SELECT case_id FROM datasets WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
        case_id = case_row["case_id"] if case_row else "UNKNOWN"

    # Registra a transformação ANTES das marcações derivadas (FK + P7).
    provenance.record_transformation(
        Transformation(
            transformation_id=transformation_id,
            case_id=case_id,
            dataset_id=dataset_id,
            rule_id="EVENT_DEDUP_V1",
            rule_version="1.0",
            parameters={"event_key": event_key},
            actor=approved_by,
            tool="deduplication_engine",
            datetime=now,
            justification=justification,
            approval=f"approved_by:{approved_by}",
            reversible=True,
            records_affected=consolidated,
        )
    )

    with connect() as conn:
        for group in consolidable:
            members = group["member_record_ids"]
            canonical = members[0]
            for rid in members:
                conn.execute(
                    """
                    INSERT INTO derived_fields (
                        derived_id, record_id, field_name, raw_value,
                        derived_value, transformation_id, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        rid,
                        "canonical_event",
                        group["event_key_value"],
                        "true" if rid == canonical else "false",
                        transformation_id,
                        "DERIVED",
                    ),
                )
    provenance.add_edge(
        "DATASET", dataset_id, "TRANSFORMATION", transformation_id, "input_to"
    )

    return {
        "transformation_id": transformation_id,
        "event_key": event_key,
        "records_marked_non_canonical": consolidated,
        "canonical_events": report["distinct_event_keys"],
        "reversible": True,
    }

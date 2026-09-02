"""Transformação: Preview + Apply (Blueprint §16, §17, §35, §43).

Fluxo obrigatório (§6): regra explícita -> impacto simulado (preview) ->
humano aprova -> serviço executa -> transformação registrada.

Materializa P2 (Derived Data Separation): o valor original permanece intacto
no RawRecord; o valor normalizado vive em DerivedField, ligado à transformação
que o produziu. O raw nunca é sobrescrito (P1).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.core.db import connect
from app.governance import provenance
from app.models.schemas import Transformation
from app.modules import rules

# Níveis de decisão humana (§43). Regras de nível 3 exigem aprovação explícita.
RULE_APPROVAL_LEVEL = {
    "CPF_NORMALIZE_V1": 1,  # reversível, baixo risco (remoção de pontuação)
    "PHONE_BR_E164_V2": 2,  # automático com revisão
}


def _records(dataset_id: str) -> list[tuple[str, dict]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT record_id, original_payload FROM raw_records WHERE dataset_id = ?",
            (dataset_id,),
        ).fetchall()
    return [(r["record_id"], json.loads(r["original_payload"])) for r in rows]


def preview(dataset_id: str, field: str, rule_id: str) -> dict:
    """Transformation Preview (§17). NÃO grava nada."""
    rule = rules.get_rule(rule_id)
    records = _records(dataset_id)
    analyzed = 0
    transformable = 0
    ambiguous = 0
    changed = 0
    samples: list[dict] = []
    for record_id, payload in records:
        if field not in payload:
            continue
        analyzed += 1
        raw_value = payload.get(field)
        outcome = rule.apply(raw_value or "")
        if outcome.ambiguous:
            ambiguous += 1
        else:
            transformable += 1
            if outcome.derived_value != raw_value:
                changed += 1
        if len(samples) < 8:
            samples.append(
                {
                    "record_id": record_id,
                    "raw_value": raw_value,
                    "derived_value": outcome.derived_value,
                    "confidence": outcome.confidence,
                    "ambiguous": outcome.ambiguous,
                    "reason": outcome.reason,
                }
            )
    return {
        "rule_id": rule.rule_id,
        "rule_version": rule.version,
        "field": field,
        "records_analyzed": analyzed,
        "transformable_auto": transformable,
        "ambiguous": ambiguous,
        "values_changed": changed,
        "originals_preserved": True,  # sempre (P1/P2)
        "approval_level": RULE_APPROVAL_LEVEL.get(rule_id, 3),
        "samples": samples,
    }


def apply(
    dataset_id: str,
    field: str,
    rule_id: str,
    *,
    approved_by: str,
    justification: str = "",
) -> dict:
    """Executa a normalização APÓS aprovação humana (§43, P9).

    Grava DerivedField (novo campo <field>_norm, P2), registra a Transformation
    no diário (§35) e adiciona arestas de proveniência (§34). Ambíguos NÃO são
    transformados: ficam sem derived_value, preservando a incerteza (P3).
    """
    rule = rules.get_rule(rule_id)
    records = _records(dataset_id)

    transformation_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    derived_field_name = f"{field}_norm"

    with connect() as conn:
        case_row = conn.execute(
            "SELECT case_id FROM datasets WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
        case_id = case_row["case_id"] if case_row else "UNKNOWN"

    # Registra a transformação ANTES dos campos derivados (FK + P7): não pode
    # existir valor derivado sem a transformação que o produziu no diário.
    outcomes = [(rid, p.get(field), rule.apply(p.get(field) or "")) for rid, p in records
                if field in p]
    affected = sum(1 for _, _, o in outcomes if o.derived_value is not None)

    provenance.record_transformation(
        Transformation(
            transformation_id=transformation_id,
            case_id=case_id,
            dataset_id=dataset_id,
            rule_id=rule.rule_id,
            rule_version=rule.version,
            parameters={"field": field, "derived_field": derived_field_name},
            actor=approved_by,
            tool="normalization_engine",
            datetime=now,
            justification=justification,
            approval=f"approved_by:{approved_by}",
            reversible=True,
            records_affected=affected,
        )
    )

    with connect() as conn:
        for record_id, raw_value, outcome in outcomes:
            conn.execute(
                """
                INSERT INTO derived_fields (
                    derived_id, record_id, field_name, raw_value,
                    derived_value, transformation_id, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    record_id,
                    derived_field_name,
                    raw_value,
                    outcome.derived_value,
                    transformation_id,
                    "DERIVED" if not outcome.ambiguous else "UNKNOWN",
                ),
            )
    # Provenance Graph: DATASET -> TRANSFORMATION -> DERIVED_FIELD(campo)
    provenance.add_edge("DATASET", dataset_id, "TRANSFORMATION", transformation_id, "input_to")
    provenance.add_edge(
        "TRANSFORMATION", transformation_id, "DERIVED_FIELD", derived_field_name, "produced"
    )

    return {
        "transformation_id": transformation_id,
        "rule_id": rule.rule_id,
        "rule_version": rule.version,
        "derived_field": derived_field_name,
        "records_affected": affected,
        "reversible": True,
    }


def list_transformations(dataset_id: str) -> list[dict]:
    """Diário de Transformação do dataset (§35)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM transformations WHERE dataset_id = ? ORDER BY datetime",
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]

"""Rollback + Dependency Graph + Invalidação Automática (Blueprint §57-59).

Materializa P10 (Reversibility). Toda transformação registrada pode ser
revertida. Reverter NÃO apaga o diário (§36, append-only): registra uma
transformação inversa e marca a original como revertida. Em seguida, propaga
a invalidação (§59): achados que dependiam do que foi revertido passam a
STALE_REQUIRES_RECOMPUTATION, em vez de continuarem sendo exibidos como válidos.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.db import connect
from app.governance import provenance
from app.models.schemas import Transformation

_STALE = "STALE_REQUIRES_RECOMPUTATION"


def list_reversible(dataset_id: str) -> list[dict]:
    """Transformações que ainda podem ser revertidas (não revertidas, não rollbacks)."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM transformations
               WHERE dataset_id = ? AND reverted_by IS NULL AND rule_id != 'ROLLBACK_V1'
               ORDER BY datetime""",
            (dataset_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def dependency_graph(dataset_id: str, transformation_id: str) -> dict:
    """Dependency Graph (§58): o que depende desta transformação."""
    forward = provenance.trace_forward("TRANSFORMATION", transformation_id)
    dependents = {"DERIVED_FIELD": [], "ENTITY": [], "FINDING": []}
    for edge in forward:
        t = edge["to"]["type"]
        if t in dependents and edge["to"]["id"] not in dependents[t]:
            dependents[t].append(edge["to"]["id"])
    # Campos derivados também são localizados pela FK direta.
    with connect() as conn:
        dfs = conn.execute(
            "SELECT DISTINCT field_name FROM derived_fields WHERE transformation_id = ?",
            (transformation_id,),
        ).fetchall()
    return {
        "transformation_id": transformation_id,
        "derived_fields": [d["field_name"] for d in dfs],
        "produced_entities": dependents["ENTITY"],
        "dependent_findings": dependents["FINDING"],
        "edges": forward,
    }


def _dependent_findings(transformation_id: str) -> list[str]:
    """Achados alcançáveis a partir da transformação (direta ou via entidades)."""
    forward = provenance.trace_forward("TRANSFORMATION", transformation_id)
    return list({e["to"]["id"] for e in forward if e["to"]["type"] == "FINDING"})


def rollback(dataset_id: str, transformation_id: str, *, actor: str,
             justification: str = "") -> dict:
    """Reverte uma transformação e invalida o que dependia dela (§57-59)."""
    with connect() as conn:
        t = conn.execute(
            "SELECT * FROM transformations WHERE transformation_id = ? AND dataset_id = ?",
            (transformation_id, dataset_id),
        ).fetchone()
    if t is None:
        raise KeyError("transformação inexistente neste dataset")
    if t["reverted_by"]:
        raise ValueError("transformação já revertida")
    if not t["reversible"]:
        raise ValueError("transformação marcada como não reversível")

    tool = t["tool"]
    undone = {"derived_fields_removed": 0, "entities_removed": 0, "memberships_removed": 0}

    # Descobre achados dependentes ANTES de remover as arestas/objetos.
    dependent_findings = _dependent_findings(transformation_id)

    with connect() as conn:
        if tool in ("normalization_engine", "deduplication_engine"):
            cur = conn.execute(
                "DELETE FROM derived_fields WHERE transformation_id = ?", (transformation_id,)
            )
            undone["derived_fields_removed"] = cur.rowcount

        elif tool == "entity_resolution_engine":
            ent_rows = conn.execute(
                """SELECT dst_id FROM provenance_edges
                   WHERE src_type='TRANSFORMATION' AND src_id=? AND dst_type='ENTITY'""",
                (transformation_id,),
            ).fetchall()
            for er in ent_rows:
                eid = er["dst_id"]
                c1 = conn.execute(
                    "DELETE FROM entity_membership WHERE entity_id = ?", (eid,)
                )
                undone["memberships_removed"] += c1.rowcount
                c2 = conn.execute("DELETE FROM entities WHERE entity_id = ?", (eid,))
                undone["entities_removed"] += c2.rowcount

    # Invalidação automática (§59): achados dependentes -> STALE.
    invalidated = []
    with connect() as conn:
        for fid in dependent_findings:
            conn.execute(
                "UPDATE findings SET status = ?, robust = NULL WHERE finding_id = ?",
                (_STALE, fid),
            )
            invalidated.append(fid)

    # Registro inverso no diário (append-only §36) e marca a original revertida.
    inverse_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    provenance.record_transformation(Transformation(
        transformation_id=inverse_id,
        case_id=t["case_id"],
        dataset_id=dataset_id,
        rule_id="ROLLBACK_V1",
        rule_version="1.0",
        parameters={"reverts": transformation_id, "original_rule": t["rule_id"]},
        actor=actor,
        tool="rollback_engine",
        datetime=now,
        justification=justification,
        approval=f"approved_by:{actor}",
        reversible=False,
        records_affected=sum(undone.values()),
    ))
    provenance.add_edge("TRANSFORMATION", inverse_id, "TRANSFORMATION",
                        transformation_id, "reverts")
    provenance.mark_transformation_reverted(transformation_id, inverse_id)

    return {
        "reverted_transformation": transformation_id,
        "original_rule": t["rule_id"],
        "inverse_transformation": inverse_id,
        "undone": undone,
        "invalidated_findings": invalidated,
        "note": ("Reversão registrada (o diário não é apagado — §36). Achados "
                 "dependentes foram marcados STALE_REQUIRES_RECOMPUTATION (§59)."),
    }

"""Testes do M5 — Rollback + Invalidação Automática (§57-59, P10).

Cobre o exemplo do blueprint (§59): um achado depende de um merge de entidade;
ao reverter o merge, o achado é automaticamente marcado STALE.
"""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-005",
    )["dataset_id"]


def test_rollback_normalization_removes_derived_and_keeps_raw(isolated_env):
    from app.core.db import connect
    from app.modules import normalization, rollback

    ds = _ingest()
    res = normalization.apply(ds, "phone", "PHONE_BR_E164_V2", approved_by="ea")
    tid = res["transformation_id"]
    with connect() as conn:
        before = conn.execute("SELECT COUNT(*) c FROM derived_fields").fetchone()["c"]
    assert before > 0

    rb = rollback.rollback(ds, tid, actor="eduardo.arcos")
    assert rb["undone"]["derived_fields_removed"] == before
    with connect() as conn:
        after = conn.execute("SELECT COUNT(*) c FROM derived_fields").fetchone()["c"]
        raw = conn.execute("SELECT COUNT(*) c FROM raw_records").fetchone()["c"]
        original = conn.execute(
            "SELECT reverted_by FROM transformations WHERE transformation_id=?", (tid,)
        ).fetchone()
    assert after == 0                 # derivados removidos
    assert raw == 72                  # raw intacto (P1)
    assert original["reverted_by"]    # marcada revertida (não apagada, §36)


def test_cannot_rollback_twice(isolated_env):
    from app.modules import normalization, rollback

    ds = _ingest()
    tid = normalization.apply(ds, "phone", "PHONE_BR_E164_V2", approved_by="ea")["transformation_id"]
    rollback.rollback(ds, tid, actor="ea")
    import pytest

    with pytest.raises(ValueError):
        rollback.rollback(ds, tid, actor="ea")


def test_merge_finding_then_rollback_invalidates(isolated_env):
    """§59: achado F depende do merge E; revertido E, F vira STALE."""
    from app.modules import eda, entity_resolution, rollback

    ds = _ingest()
    resolved = entity_resolution.resolve(ds)
    ents = resolved["entities"]
    a, b = ents[0]["entity_id"], ents[1]["entity_id"]

    decision = entity_resolution.decide(ds, a, b, "MATCH", approved_by="ea")
    merged = decision["merged_entity_id"]
    assert merged

    finding = eda.entity_aggregate_finding(ds, merged)
    fid = finding["finding_id"]

    # A transformação da decisão de entidade.
    reversible = rollback.list_reversible(ds)
    ent_tx = next(t for t in reversible if t["tool"] == "entity_resolution_engine")

    # Dependency graph deve listar o achado.
    dep = rollback.dependency_graph(ds, ent_tx["transformation_id"])
    assert fid in dep["dependent_findings"]

    rb = rollback.rollback(ds, ent_tx["transformation_id"], actor="eduardo.arcos")
    assert fid in rb["invalidated_findings"]
    assert rb["undone"]["entities_removed"] == 1

    findings = {f["finding_id"]: f for f in eda.list_findings(ds)}
    assert findings[fid]["status"] == "STALE_REQUIRES_RECOMPUTATION"


def test_dependency_graph_lists_derived_fields(isolated_env):
    from app.modules import normalization, rollback

    ds = _ingest()
    tid = normalization.apply(ds, "phone", "PHONE_BR_E164_V2", approved_by="ea")["transformation_id"]
    dep = rollback.dependency_graph(ds, tid)
    assert "phone_norm" in dep["derived_fields"]

"""Testes do M10 — Métricas formais de validação (§62-67)."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-MET",
    )["dataset_id"]


def test_entity_resolution_zero_false_merge(isolated_env):
    """Objetivo de qualidade central (§85): nenhum false merge."""
    from app.modules import metrics

    m = metrics.entity_resolution_metrics(_ingest())
    # O par Carlos A×B deve ser NON_MATCH correto -> false_merge_rate 0.
    assert m["false_merge_rate"] == 0.0
    assert m["confusion"]["fp"] == 0
    # Há homônimos gold distintos (2 Carlos) e o sistema os separa (tn>=1).
    assert m["confusion"]["tn"] >= 1


def test_dedup_metrics_detect_technical_duplicates(isolated_env):
    from app.modules import metrics

    m = metrics.deduplication_metrics(_ingest())
    assert m["raw_rows"] == 72
    assert m["canonical_events"] < 72                # houve redução
    assert m["technical_duplicate_groups"] >= 1


def test_reproducibility_rate_is_one(isolated_env):
    """Operações determinísticas reproduzem exatamente (§64)."""
    from app.modules import metrics

    m = metrics.reproducibility_rate(_ingest())
    assert m["rate"] == 1.0
    assert all(m["checks"].values())


def test_transformation_metrics(isolated_env):
    from app.modules import metrics, normalization

    ds = _ingest()
    normalization.apply(ds, "phone", "PHONE_BR_E164_V2", approved_by="ea")
    m = metrics.transformation_metrics(ds)
    assert m["total"] == 1
    assert m["reversibility_rate"] == 1.0
    assert m["error_rate"] == 0.0


def test_full_report_has_all_sections(isolated_env):
    from app.modules import eda, metrics

    ds = _ingest()
    eda.detect_temporal_peak(ds)
    rep = metrics.full_report(ds)
    assert set(rep) == {
        "transformation", "entity_resolution", "deduplication",
        "provenance_completeness", "reproducibility",
    }
    assert rep["provenance_completeness"]["pc"] == 1.0


def test_llm_evaluation_criteria(isolated_env):
    from app.modules import metrics, rag

    rag.seed_kb()
    ds = _ingest()
    ev = metrics.llm_evaluation(ds)
    # O assistente preserva incerteza, recusa overclaim e aplica guardrail causal.
    assert ev["per_criterion"]["uncertainty_preservation"] == 1.0
    assert ev["per_criterion"]["causal_reasoning"] == 1.0
    assert ev["per_criterion"]["entity_conflation_avoidance"] == 1.0
    assert ev["overall_pass_rate"] >= 0.8

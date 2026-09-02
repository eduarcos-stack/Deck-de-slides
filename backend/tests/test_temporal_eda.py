"""Testes do M4 — Temporal Engine (§18-19), EDA/Findings (§28-33) e
Adversarial Auditor (§41). Cobre a demonstração §89-90: um pico 00h-02h que
não sobrevive a um parsing temporal mais estrito.
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
        operator="perito", case_id="CASE-004",
    )["dataset_id"]


def test_temporal_parse_midnight_ambiguity():
    from app.modules import temporal

    naive = temporal.parse("15/08/2024 24:00", mode="naive")
    assert naive.local_hour == 0  # colapsado para meia-noite (§89)

    strict = temporal.parse("15/08/2024 24:00", mode="strict")
    assert strict.local_hour is None  # incerteza preservada (P3)
    assert strict.clock_quality == "UNKNOWN"


def test_temporal_offset_not_validated():
    from app.modules import temporal

    tp = temporal.parse("2024-08-15T14:20:00-03:00", mode="strict")
    assert tp.parsed and tp.local_hour == 14
    assert tp.timezone_source == "explicit"
    assert "não validado" in tp.note  # §19, P6


def test_hour_distribution_peak_only_under_naive(isolated_env):
    from app.modules import eda

    ds = _ingest()
    naive = eda.hour_distribution(ds, "naive")
    strict = eda.hour_distribution(ds, "strict")
    # Sob parser naive, os 2 registros 24:00 caem em 00h, criando o pico.
    assert naive["window_00_02h"] == 2
    # Sob parser strict, eles são excluídos: o pico some.
    assert strict["window_00_02h"] == 0


def test_pattern_stability_not_robust(isolated_env):
    from app.modules import eda

    ds = _ingest()
    stab = eda.pattern_stability(ds)
    assert stab["scenario_naive"] == 2
    assert stab["scenario_strict"] == 0
    assert stab["robust"] is False


def test_detect_peak_and_adversarial_audit(isolated_env):
    from app.modules import adversarial, eda

    ds = _ingest()
    finding = eda.detect_temporal_peak(ds)
    assert finding["status"] == "EXPLORATORY_FINDING"
    assert len(finding["pattern_provenance"]) == 2  # os 2 registros de meia-noite

    audit = adversarial.audit_finding(ds, finding["finding_id"])
    assert audit["verdict"] == "NÃO ROBUSTO"
    assert audit["robust"] is False
    # A robustez do achado foi persistida como False.
    persisted = {f["finding_id"]: f for f in eda.list_findings(ds)}
    assert persisted[finding["finding_id"]]["robust"] is False


def test_outlier_policy_present(isolated_env):
    from app.modules import eda

    ds = _ingest()
    res = eda.outliers(ds, "amount")
    assert "Outlier ≠ ilicitude" in res["policy"]


def test_support_challenge_synthesis_cautious():
    from app.modules import adversarial

    r = adversarial.support_challenge_synthesis(
        "Carlos A e B são a mesma pessoa",
        support=["nome idêntico"],
        challenge=["CPF conflita", "nascimento conflita"],
    )
    assert "cautela" in r["synthesis"]

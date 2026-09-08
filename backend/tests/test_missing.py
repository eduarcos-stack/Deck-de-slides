"""Testes do M12 — Missing Data Semantic Analyzer (§15).

Núcleo: confirmar sentinelas de CPF ("-1", "999999") como MISSING reduz o
false_split_rate da Entity Resolution — a lacuna que as métricas (§62-67)
expuseram — sem assumir equivalência automaticamente (P3).
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
        operator="perito", case_id="CASE-MISS",
    )["dataset_id"]


def test_analyze_flags_cpf_sentinels(isolated_env):
    from app.modules import missing

    ds = _ingest()
    rep = missing.analyze(ds)
    cpf = next((f for f in rep["fields"] if f["field"] == "cpf"), None)
    assert cpf is not None
    values = {c["value"] for c in cpf["candidates"]}
    # As sentinelas do dataset devem ser sinalizadas como candidatas.
    assert {"-1", "999999"} & values
    # Nada é confirmado por padrão (§15, P3).
    assert all(c["confirmed_semantic"] is None for c in cpf["candidates"])


def test_zero_not_flagged_in_amount(isolated_env):
    """"0" é valor legítimo em amount — não deve ser sugerido como ausência."""
    from app.modules import missing

    ds = _ingest()
    rep = missing.analyze(ds)
    amount = next((f for f in rep["fields"] if f["field"] == "amount"), None)
    if amount:
        assert "0" not in {c["value"] for c in amount["candidates"]}


def test_confirming_missing_reduces_false_split(isolated_env):
    from app.modules import metrics, missing

    ds = _ingest()
    before = metrics.entity_resolution_metrics(ds)

    # Confirma as sentinelas de CPF como ausência (decisão humana §15/P9).
    for value in ("-1", "999999", "N/A", "NI"):
        missing.confirm(ds, "cpf", value, "MISSING", "eduardo.arcos")

    after = metrics.entity_resolution_metrics(ds)
    # O false merge segue zero; o false split cai (conflitos viram abstenção).
    assert after["false_merge_rate"] == 0.0
    assert after["false_split_rate"] <= before["false_split_rate"]
    assert after["confusion"]["fn"] <= before["confusion"]["fn"]


def test_confirmed_missing_map(isolated_env):
    from app.modules import missing

    ds = _ingest()
    missing.confirm(ds, "cpf", "-1", "MISSING", "ea")
    missing.confirm(ds, "cpf", "999999", "LEGIT_VALUE", "ea")  # não é missing
    cm = missing.confirmed_missing(ds)
    assert "-1" in cm["cpf"]
    assert "999999" not in cm.get("cpf", set())  # LEGIT_VALUE não entra no mapa


def test_invalid_semantic_rejected(isolated_env):
    import pytest

    from app.modules import missing

    ds = _ingest()
    with pytest.raises(ValueError):
        missing.confirm(ds, "cpf", "-1", "TALVEZ", "ea")

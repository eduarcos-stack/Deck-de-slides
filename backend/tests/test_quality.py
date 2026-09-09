"""Testes do M13 — Quality Analyzer (§14)."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-QA",
    )["dataset_id"]


def test_quality_has_seven_dimensions(isolated_env):
    from app.modules import quality

    rep = quality.analyze(_ingest())
    assert set(rep["dimensions"]) == {
        "completude", "acuracia_potencial", "consistencia", "validade",
        "unicidade", "atualidade", "proveniencia",
    }
    assert rep["overall"] is not None
    assert rep["dimensions"]["proveniencia"]["score"] == 1.0  # todo raw tem fonte


def test_completude_below_one_due_to_sentinels(isolated_env):
    from app.modules import quality

    rep = quality.analyze(_ingest())
    # Há sentinelas de CPF e notes vazias -> completude < 1.
    assert rep["dimensions"]["completude"]["score"] < 1.0


def test_divergence_flagged_not_as_error():
    """§14: valores discordantes de uma mesma entidade não viram 'erro'."""
    from app.modules import quality

    payloads = [
        {"name": "Fulano X", "dob": "01/01/1990", "cpf": "111.111.111-11",
         "company": "Alfa", "city": "Vitória"},
        {"name": "Fulano X", "dob": "01/01/1990", "cpf": "111.111.111-11",
         "company": "Alfa", "city": "Serra"},  # cidade diverge
    ]
    cons, divs = quality._consistency(payloads, list(payloads[0].keys()), {})
    assert cons < 1.0
    assert len(divs) == 1
    assert divs[0]["field"] == "city"
    assert divs[0]["classification"] == "DIVERGENCE_NOT_ERROR"
    assert "não" in divs[0]["message"].lower() and "erro" in divs[0]["message"].lower()


def test_missing_value_is_not_a_divergence():
    """Um valor ausente (sentinela) não conta como divergência (coerência com §15)."""
    from app.modules import quality

    payloads = [
        {"name": "Beltrano", "dob": "02/02/1985", "cpf": "222.222.222-22",
         "company": "Beta", "city": "Vitória"},
        {"name": "Beltrano", "dob": "02/02/1985", "cpf": "N/A",
         "company": "Beta", "city": "Vitória"},  # cpf ausente, não divergente
    ]
    cons, divs = quality._consistency(payloads, list(payloads[0].keys()), {})
    assert cons == 1.0
    assert divs == []


def test_illicit_matrix_has_no_false_divergence(isolated_env):
    """No caso sintético, empresa/cidade são estáveis por pessoa: 0 divergências falsas."""
    from app.modules import quality

    rep = quality.analyze(_ingest())
    assert rep["divergences"] == []
    assert rep["dimensions"]["consistencia"]["score"] == 1.0

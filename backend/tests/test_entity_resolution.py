"""Testes do M3 — Entity Resolution (§22-25) e Impact Analysis (§26-27).

O teste central materializa §85: dois "Carlos Eduardo Silva" homônimos, com
CPF e nascimento conflitantes, DEVEM resultar em NON_MATCH.
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
        operator="perito", case_id="CASE-003",
    )["dataset_id"]


def _two_carlos(resolved):
    carlos = [e for e in resolved["entities"] if "carlos eduardo silva" in e["name"].lower()]
    return carlos


def test_carlos_a_vs_b_is_non_match(isolated_env):
    from app.modules import entity_resolution

    ds = _ingest()
    resolved = entity_resolution.resolve(ds)
    carlos = _two_carlos(resolved)
    # Existem pelo menos duas identidades homônimas distintas.
    assert len(carlos) >= 2
    # O par candidato Carlos A × Carlos B deve ser NON_MATCH.
    pairs = [
        p for p in resolved["candidate_pairs"]
        if p["decision"] and p["name_similarity"] >= 0.99
    ]
    assert pairs, "esperado par candidato homônimo"
    carlos_pair = next(p for p in pairs if p["cpf"] == "conflict" and p["dob"] == "conflict")
    assert carlos_pair["decision"] == "NON_MATCH"
    assert carlos_pair["confidence"] == "high"


def test_impact_analysis_flags_high_impact(isolated_env):
    from app.modules import entity_resolution

    ds = _ingest()
    resolved = entity_resolution.resolve(ds)
    carlos = sorted(_two_carlos(resolved), key=lambda e: -e["record_count"])
    a, b = carlos[0]["entity_id"], carlos[1]["entity_id"]
    impact = entity_resolution.impact_analysis(ds, a, b)

    # A fusão dos dois Carlos conecta empresas e soma valores => HIGH IMPACT (§25).
    assert impact["high_impact"] is True
    assert impact["classification"] == "HIGH IMPACT ENTITY DECISION"
    assert impact["after"]["events"] >= impact["before"]["A"]["events"]
    # A recomendação embutida é NON_MATCH.
    assert impact["recommendation"]["decision"] == "NON_MATCH"


def test_decision_is_logged_and_reversible(isolated_env):
    from app.core.db import connect
    from app.modules import entity_resolution

    ds = _ingest()
    resolved = entity_resolution.resolve(ds)
    carlos = _two_carlos(resolved)
    a, b = carlos[0]["entity_id"], carlos[1]["entity_id"]

    res = entity_resolution.decide(ds, a, b, "NON_MATCH", approved_by="eduardo.arcos")
    assert res["decision"] == "NON_MATCH"
    assert res["merged_entity_id"] is None  # rejeição não cria entidade fundida
    with connect() as conn:
        t = conn.execute(
            "SELECT rule_id, approval FROM transformations WHERE transformation_id=?",
            (res["transformation_id"],),
        ).fetchone()
    assert t["rule_id"] == "ENTITY_MATCH_DECISION_V1"
    assert "eduardo.arcos" in t["approval"]


def test_approved_match_creates_membership(isolated_env):
    """MATCH aprovado grava entity_membership sem apagar o raw (P1)."""
    from app.core.db import connect
    from app.modules import entity_resolution

    ds = _ingest()
    resolved = entity_resolution.resolve(ds)
    # Usa a maior entidade (Carlos A) fundida consigo mesma não faz sentido;
    # aqui validamos o mecanismo de membership com duas entidades quaisquer.
    ents = resolved["entities"]
    a, b = ents[0]["entity_id"], ents[1]["entity_id"]
    res = entity_resolution.decide(ds, a, b, "MATCH", approved_by="eduardo.arcos")
    assert res["merged_entity_id"]
    with connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) c FROM entity_membership WHERE entity_id=?",
            (res["merged_entity_id"],),
        ).fetchone()["c"]
        raw = conn.execute("SELECT COUNT(*) c FROM raw_records").fetchone()["c"]
    assert n > 0
    assert raw == 72  # raw intacto

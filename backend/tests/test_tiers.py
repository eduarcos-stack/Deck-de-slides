"""Testes do M14 — Tiers de modelo (§50)."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-TIER",
    )["dataset_id"]


def test_tier_profiles_and_capabilities():
    from app.modules import orchestrator

    st = orchestrator.tier_status()
    assert set(st["profiles"]) == {"workstation", "server"}
    # Servidor cobre capacidades de raciocínio complexo que a workstation não lista.
    assert "adversarial analysis" in st["profiles"]["server"]["capabilities"]
    assert "adversarial analysis" not in st["profiles"]["workstation"]["capabilities"]
    assert st["profiles"]["server"]["max_context_tokens"] > st["profiles"]["workstation"]["max_context_tokens"]


def test_tier_serves_ordering():
    from app.modules import orchestrator

    assert orchestrator.tier_serves("server", "workstation") is True
    assert orchestrator.tier_serves("server", "server") is True
    assert orchestrator.tier_serves("workstation", "server") is False


def test_default_tier_is_workstation(monkeypatch):
    from app.modules import orchestrator

    monkeypatch.delenv("TRACELM_LLM_TIER", raising=False)
    assert orchestrator.current_tier() == "workstation"


def test_adversarial_recommends_server(isolated_env, monkeypatch):
    """Tarefa causal (Adversarial Auditor) recomenda o tier servidor (§50)."""
    from app.modules import orchestrator

    monkeypatch.setenv("TRACELM_LLM_TIER", "workstation")
    r = orchestrator.ask("A correlação prova causalidade?", None, "ea")
    assert r["role"] == "Adversarial Auditor"
    assert r["tier"]["recommended"] == "server"
    assert r["tier"]["served"] is False  # workstation atende de forma limitada


def test_profiler_served_by_workstation(isolated_env, monkeypatch):
    from app.modules import orchestrator

    monkeypatch.setenv("TRACELM_LLM_TIER", "workstation")
    ds = _ingest()
    r = orchestrator.ask("faça o profiling desta base", ds, "ea")
    assert r["tier"]["recommended"] == "workstation"
    assert r["tier"]["served"] is True


def test_model_agnostic_server_tier_serves_everything(isolated_env, monkeypatch):
    """Trocar o tier via env (model-agnostic §50) não quebra nada e atende tudo."""
    from app.modules import orchestrator

    monkeypatch.setenv("TRACELM_LLM_TIER", "server")
    r = orchestrator.ask("A correlação prova causalidade?", None, "ea")
    assert r["tier"]["current"] == "server"
    assert r["tier"]["served"] is True

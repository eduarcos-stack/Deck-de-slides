"""Testes do M9 — RAG local (§51) e LLM Orchestrator (§37-40, §92)."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest():
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-LLM",
    )["dataset_id"]


def test_rag_seeds_and_retrieves(isolated_env):
    from app.modules import rag

    n = rag.seed_kb()
    assert n >= 4
    res = rag.search("dois identificadores discriminantes conflitantes", k=2)
    assert res and res[0]["score"] > 0
    # o doc de metodologia de ER deve estar entre os mais relevantes
    assert any("entity" in r["source"].lower() or "resolution" in r["title"].lower()
               for r in res)


def test_rag_domain_not_case_data(isolated_env):
    """RAG traz conhecimento de domínio, não registros do caso (§51)."""
    from app.modules import rag

    rag.seed_kb()
    res = rag.search("cpf", k=3)
    for r in res:
        assert r["source"].endswith(".md")  # documentos de conhecimento, não linhas


def test_orchestrator_carlos_differential(isolated_env):
    """§92: resposta epistemológica, não 'chat com planilha'."""
    from app.modules import orchestrator, rag

    rag.seed_kb()
    ds = _ingest()
    r = orchestrator.ask("Quantas transações Carlos Eduardo Silva realizou?", ds, "ea")
    assert r["intent"] in ("transactions", "entity")
    assert r["role"] == "Entity Analyst"
    # Não afirma um número único consolidado; menciona homônimos e eventos.
    assert "homônimos" in r["answer"] or "homonim" in r["answer"].lower()
    assert "NÃO é suportada" in r["answer"]
    assert any("Similaridade de nome não é identidade" in g for g in r["guardrails"])


def test_orchestrator_causal_guardrail(isolated_env):
    from app.modules import orchestrator

    r = orchestrator.ask("A correlação de 0,88 prova que Carlos fez as transferências?",
                         None, "ea")
    assert r["intent"] == "causal"
    assert "causal" in r["answer"].lower()
    assert any("causalidade" in g.lower() for g in r["guardrails"])


def test_orchestrator_llm_not_execution_engine(isolated_env):
    """A nota deixa explícito que o LLM não é motor de execução (§4)."""
    from app.modules import orchestrator, rag

    rag.seed_kb()
    ds = _ingest()
    r = orchestrator.ask("faça o profiling desta base", ds, "ea")
    assert r["provider"] == "local-deterministic"
    assert "motor de execução" in r["note"]
    assert "profiling.profile_dataset" in r["plan"]

"""Testes das melhorias locais do assistente (§37-40, §51).

Cobrem: nova intenção de agregação de valores, robustez a acentos no
classificador, e a busca RAG com normalização/stemming/sinônimos — tudo
determinístico e local (§47), sem embeddings nem rede.
"""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest(case_id: str = "CASE-SEM"):
    from app.modules import ingestion

    return ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id=case_id,
    )["dataset_id"]


# --------------------------------------------------------------------------- #
# Classificador de intenção
# --------------------------------------------------------------------------- #
def test_aggregate_intent_matches_money_questions():
    from app.modules import orchestrator

    assert orchestrator._classify("Quanto foi movimentado em reais nas transações?") == "aggregate"
    assert orchestrator._classify("Qual o montante total?") == "aggregate"
    assert orchestrator._classify("Some os valores em R$") == "aggregate"


def test_transactions_not_shadowed_by_aggregate():
    from app.modules import orchestrator

    # Pergunta de contagem/entidade não deve cair em agregação de valores.
    assert orchestrator._classify("Quantas transações Carlos realizou?") == "transactions"


def test_classifier_is_accent_insensitive():
    from app.modules import orchestrator

    assert orchestrator._classify("analise temporal") == "temporal"
    assert orchestrator._classify("análise temporal") == "temporal"
    assert orchestrator._classify("ausencia de dados") == "profile"


def test_aggregate_answer_sums_amount(isolated_env):
    from app.modules import orchestrator

    ds = _ingest()
    r = orchestrator.ask("Quanto foi movimentado em reais nas transações?", ds, "ea")
    assert r["intent"] == "aggregate"
    assert r["role"] == "EDA Analyst"
    assert "R$" in r["answer"]
    assert "raw_records.sum(amount)" in r["plan"]
    # Guardrail epistemológico presente (bruto ≠ evento; ausência ≠ zero).
    assert any("bruta" in g.lower() or "ausent" in g.lower() for g in r["guardrails"])


def test_brl_formatting():
    from app.modules import orchestrator

    assert orchestrator._brl(1234567.8) == "R$ 1.234.567,80"
    assert orchestrator._brl(0) == "R$ 0,00"


# --------------------------------------------------------------------------- #
# RAG local
# --------------------------------------------------------------------------- #
def test_rag_accent_insensitive(isolated_env):
    from app.modules import rag

    rag.seed_kb()
    a = rag.search("transação")
    b = rag.search("transacao")
    assert a and b
    assert {r["doc_id"] for r in a} == {r["doc_id"] for r in b}


def test_rag_synonym_expansion_recovers_valor(isolated_env):
    """'movimentado' (sem a palavra 'valor') recupera o doc que fala de valor."""
    from app.modules import rag

    rag.seed_kb()
    res = rag.search("Quanto foi movimentado?")
    assert res, "a expansão por sinônimos deveria recuperar algo"
    titles = " ".join(r["title"].lower() for r in res)
    snippets = " ".join(r["snippet"].lower() for r in res)
    assert "valor" in snippets or "campo" in titles


def test_rag_stemming_matches_plural(isolated_env):
    from app.modules import rag

    rag.seed_kb()
    singular = rag.search("homônimo")
    plural = rag.search("homônimos")
    assert singular and plural
    assert singular[0]["doc_id"] == plural[0]["doc_id"]

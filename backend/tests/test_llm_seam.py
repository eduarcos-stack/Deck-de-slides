"""Testes do seam model-agnostic (§50): provider generativo remoto + embeddings.

Tudo desligado por padrão. Aqui o endpoint é mockado (sem rede real) para
verificar: seleção de provider, composição remota, FALLBACK local em falha, e o
caminho de embeddings do RAG com fallback para TF-IDF.
"""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


# --------------------------------------------------------------------------- #
# Provider generativo (orchestrator)
# --------------------------------------------------------------------------- #
def test_default_provider_is_local(monkeypatch):
    from app.modules import orchestrator

    monkeypatch.delenv("TRACELM_LLM_PROVIDER", raising=False)
    assert orchestrator.get_provider().name == "local-deterministic"


def test_remote_provider_selected(monkeypatch):
    from app.modules import orchestrator

    monkeypatch.setenv("TRACELM_LLM_PROVIDER", "remote")
    assert orchestrator.get_provider().name == "remote-openai-compatible"


def test_remote_compose_uses_model_text(monkeypatch):
    from app.modules import orchestrator

    monkeypatch.setenv("TRACELM_LLM_ENDPOINT", "http://enclave.local/v1/chat/completions")
    monkeypatch.setattr(orchestrator, "_http_json", lambda url, payload, timeout: {
        "choices": [{"message": {"content": "Explicação didática preservando os números."}}]
    })
    out = orchestrator.RemoteOpenAICompatibleProvider().compose(
        {"draft_answer": "total R$ 10,00", "guardrails": ["g"], "question": "quanto?"})
    assert out == "Explicação didática preservando os números."


def test_remote_compose_falls_back_on_error(monkeypatch):
    from app.modules import orchestrator

    monkeypatch.setenv("TRACELM_LLM_ENDPOINT", "http://enclave.local/v1/chat/completions")

    def boom(url, payload, timeout):
        raise OSError("endpoint fora do ar")

    monkeypatch.setattr(orchestrator, "_http_json", boom)
    out = orchestrator.RemoteOpenAICompatibleProvider().compose({"draft_answer": "FATO DETERMINÍSTICO"})
    assert out == "FATO DETERMINÍSTICO"     # nunca quebra (§4)


def test_remote_compose_without_endpoint_is_local(monkeypatch):
    from app.modules import orchestrator

    monkeypatch.delenv("TRACELM_LLM_ENDPOINT", raising=False)
    out = orchestrator.RemoteOpenAICompatibleProvider().compose({"draft_answer": "LOCAL"})
    assert out == "LOCAL"


def test_ask_uses_remote_provider_end_to_end(isolated_env, monkeypatch):
    from app.modules import ingestion, orchestrator

    monkeypatch.setenv("TRACELM_LLM_PROVIDER", "remote")
    monkeypatch.setenv("TRACELM_LLM_ENDPOINT", "http://enclave.local/v1/chat/completions")
    monkeypatch.setattr(orchestrator, "_http_json", lambda url, payload, timeout: {
        "choices": [{"message": {"content": "RESPOSTA DO MODELO"}}]})
    ds = ingestion.ingest(content=DATASET.read_bytes(), filename="im.csv",
                          extension=".csv", operator="p", case_id="CASE-SEAM")["dataset_id"]
    r = orchestrator.ask("faça o profiling desta base", ds, "ea")
    assert r["provider"] == "remote-openai-compatible"
    assert r["answer"] == "RESPOSTA DO MODELO"


# --------------------------------------------------------------------------- #
# Embeddings no RAG
# --------------------------------------------------------------------------- #
def test_rag_uses_embeddings_when_configured(isolated_env, monkeypatch):
    from app.modules import rag

    rag.seed_kb()
    monkeypatch.setenv("TRACELM_EMBEDDINGS_ENDPOINT", "http://enclave.local/v1/embeddings")

    # Embedding fake: termos EXCLUSIVOS do doc de metodologia (blocking/jaro/
    # non_match) alinham query e doc ao eixo [1,0]; os demais ficam ortogonais.
    def fake_embed(texts):
        vecs = []
        for t in texts:
            low = t.lower()
            hit = any(w in low for w in ["blocking", "jaro", "non_match"])
            vecs.append([1.0, 0.0] if hit else [0.0, 1.0])
        return vecs

    monkeypatch.setattr(rag, "_embed_texts", fake_embed)
    res = rag.search("blocking com jaro-winkler resulta em non_match")
    assert res
    assert "entity_resolution" in res[0]["source"].lower()


def test_rag_embeddings_falls_back_to_tfidf(isolated_env, monkeypatch):
    from app.modules import rag

    rag.seed_kb()
    monkeypatch.setenv("TRACELM_EMBEDDINGS_ENDPOINT", "http://enclave.local/v1/embeddings")

    def boom(texts):
        raise OSError("sem embeddings")

    monkeypatch.setattr(rag, "_embed_texts", boom)
    # Cai no TF-IDF local e ainda recupera algo relevante.
    res = rag.search("entity resolution identidade")
    assert res

"""API do TRACE-LM — MVP (Blueprint §37, §44).

Local-first (§47): a API roda na workstation/servidor institucional; por padrão
nada é enviado a serviço externo. O LLM não tem acesso direto à base — esta
camada expõe apenas os serviços determinísticos das capacidades 1-3 do MVP.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from app.core.db import connect, init_db
from app.governance import provenance
from app.modules import (
    adversarial,
    deduplication,
    eda,
    entity_resolution,
    ingestion,
    normalization,
    profiling,
    rollback,
    rules,
    temporal,
)

app = FastAPI(
    title="TRACE-LM API",
    version="0.1.0-mvp-m1",
    description=(
        "Transformação Rastreável e Análise Confiável de Evidências. "
        "AI-assisted, human-controlled, provenance-first."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local-first: front e back na mesma máquina/LAN
    allow_methods=["*"],
    allow_headers=["*"],
)

# Garante o schema local assim que a aplicação é carregada (não depende do
# evento de startup, que não dispara em TestClient sem context manager).
init_db()


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "principle": "provenance-first"}


@app.post("/ingest")
async def ingest_file(
    file: UploadFile,
    operator: str = Form(...),
    case_id: str = Form(...),
) -> dict:
    """Capacidade 1 — Ingestão (§10). Preserva o raw e cria registros imutáveis."""
    content = await file.read()
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".csv", ".tsv", ".json", ".jsonl", ".xls", ".xlsx"}:
        raise HTTPException(400, f"Extensão não suportada: {extension}")
    try:
        result = ingestion.ingest(
            content=content,
            filename=file.filename or "sem_nome",
            extension=extension,
            operator=operator,
            case_id=case_id,
            mime_type=file.content_type or "application/octet-stream",
        )
    except ingestion.IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "message": f"{result['row_count']} registros recebidos. "
        "Nenhuma transformação realizada.",
        **result,
    }


@app.get("/cases/{case_id}/datasets")
def list_datasets(case_id: str) -> dict:
    """Lista os datasets de um caso (aba DATA — §44)."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.dataset_id, d.version, d.created_at,
                   s.filename, s.row_count, s.column_count, s.hash, s.operator
            FROM datasets d JOIN sources s ON s.source_id = d.source_id
            WHERE d.case_id = ?
            ORDER BY d.created_at DESC
            """,
            (case_id,),
        ).fetchall()
    return {"case_id": case_id, "datasets": [dict(r) for r in rows]}


@app.get("/datasets/{dataset_id}/profile")
def get_profile(dataset_id: str) -> dict:
    """Capacidade 3 — Profiling (§13). Somente-leitura, sem transformação."""
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM datasets WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(404, "Dataset não encontrado.")
    return profiling.profile_dataset(dataset_id).model_dump()


@app.get("/datasets/{dataset_id}/records")
def get_records(dataset_id: str, limit: int = 100, offset: int = 0) -> dict:
    """Retorna registros brutos (aba DATA). Payload imutável, tal como recebido."""
    import json

    with connect() as conn:
        rows = conn.execute(
            "SELECT record_id, original_payload, hash, status FROM raw_records "
            "WHERE dataset_id = ? LIMIT ? OFFSET ?",
            (dataset_id, limit, offset),
        ).fetchall()
    return {
        "dataset_id": dataset_id,
        "records": [
            {
                "record_id": r["record_id"],
                "hash": r["hash"],
                "status": r["status"],
                "payload": json.loads(r["original_payload"]),
            }
            for r in rows
        ],
    }


# --------------------------------------------------------------------------- #
# Milestone 2 — Transformação (§16-17, §20, §35, §43)
# --------------------------------------------------------------------------- #
class ApplyBody(BaseModel):
    field: str
    rule_id: str
    approved_by: str
    justification: str = ""


class DedupApplyBody(BaseModel):
    event_key: str
    approved_by: str
    justification: str = ""


@app.get("/rules")
def get_rules() -> dict:
    """Motor de Regras (§52): regras determinísticas com ID + versão."""
    return {"rules": rules.list_rules()}


@app.get("/datasets/{dataset_id}/normalize/preview")
def normalize_preview(dataset_id: str, field: str, rule_id: str) -> dict:
    """Capacidade 4 — Transformation Preview (§17). Não grava nada."""
    _require_dataset(dataset_id)
    try:
        return normalization.preview(dataset_id, field, rule_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/datasets/{dataset_id}/normalize/apply")
def normalize_apply(dataset_id: str, body: ApplyBody) -> dict:
    """Capacidade 4 — Apply após aprovação humana (§43, P9)."""
    _require_dataset(dataset_id)
    if not body.approved_by.strip():
        raise HTTPException(422, "Aprovação humana exige identificação do operador (P9).")
    try:
        return normalization.apply(
            dataset_id,
            body.field,
            body.rule_id,
            approved_by=body.approved_by,
            justification=body.justification,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/datasets/{dataset_id}/dedup")
def dedup_analyze(dataset_id: str, event_key: str) -> dict:
    """Capacidade 5 — Deduplicação por unidade de evento (§20). Somente-leitura."""
    _require_dataset(dataset_id)
    try:
        return deduplication.analyze(dataset_id, event_key)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/datasets/{dataset_id}/dedup/canonicalize")
def dedup_canonicalize(dataset_id: str, body: DedupApplyBody) -> dict:
    """Capacidade 5 — Consolidação após aprovação (§43). Não apaga o raw (P1)."""
    _require_dataset(dataset_id)
    if not body.approved_by.strip():
        raise HTTPException(422, "Consolidação exige aprovação humana (P9).")
    try:
        return deduplication.canonicalize(
            dataset_id,
            body.event_key,
            approved_by=body.approved_by,
            justification=body.justification,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/datasets/{dataset_id}/transformations")
def get_transformations(dataset_id: str) -> dict:
    """Diário de Transformação do dataset (§35)."""
    _require_dataset(dataset_id)
    return {"dataset_id": dataset_id, "transformations": normalization.list_transformations(dataset_id)}


def _require_dataset(dataset_id: str) -> None:
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM datasets WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()
    if not exists:
        raise HTTPException(404, "Dataset não encontrado.")


# --------------------------------------------------------------------------- #
# Milestone 3 — Entity Resolution, Impact Analysis e Auditoria (§22-27, §34, §45)
# --------------------------------------------------------------------------- #
class ImpactBody(BaseModel):
    entity_a: str
    entity_b: str


class DecideBody(BaseModel):
    entity_a: str
    entity_b: str
    decision: str  # MATCH | NON_MATCH | POSSIBLE
    approved_by: str
    justification: str = ""


@app.get("/datasets/{dataset_id}/entities")
def get_entities(dataset_id: str) -> dict:
    """Capacidade 6 — Entity Resolution (§22). Entidades candidatas + pares."""
    _require_dataset(dataset_id)
    return entity_resolution.resolve(dataset_id)


@app.get("/datasets/{dataset_id}/entities/compare")
def compare_records(dataset_id: str, a: str, b: str) -> dict:
    """Matriz de comparação entre dois registros (§24)."""
    _require_dataset(dataset_id)
    try:
        return entity_resolution.compare_records(dataset_id, a, b)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/datasets/{dataset_id}/entities/impact")
def entity_impact(dataset_id: str, body: ImpactBody) -> dict:
    """Impact Analysis before/after de uma fusão proposta (§26-27)."""
    _require_dataset(dataset_id)
    try:
        return entity_resolution.impact_analysis(dataset_id, body.entity_a, body.entity_b)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/datasets/{dataset_id}/entities/decide")
def entity_decide(dataset_id: str, body: DecideBody) -> dict:
    """Decisão humana sobre a fusão (§43 nível 3, P9). Auditável e reversível."""
    _require_dataset(dataset_id)
    if not body.approved_by.strip():
        raise HTTPException(422, "Decisão de identidade exige aprovação humana (P9).")
    try:
        return entity_resolution.decide(
            dataset_id, body.entity_a, body.entity_b, body.decision,
            approved_by=body.approved_by, justification=body.justification,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/datasets/{dataset_id}/provenance")
def get_provenance(dataset_id: str) -> dict:
    """Provenance Graph do dataset (§34): arestas + diário de transformação."""
    _require_dataset(dataset_id)
    with connect() as conn:
        edges = conn.execute(
            """SELECT src_type, src_id, dst_type, dst_id, relation, created_at
               FROM provenance_edges ORDER BY edge_id"""
        ).fetchall()
    return {
        "dataset_id": dataset_id,
        "edges": [dict(e) for e in edges],
        "transformations": normalization.list_transformations(dataset_id),
    }


@app.get("/provenance/trace")
def trace(object_type: str, object_id: str) -> dict:
    """Botão "Como chegamos aqui?" (§45): caminho reverso até a fonte."""
    return {
        "object": {"type": object_type, "id": object_id},
        "path": provenance.trace_back(object_type, object_id),
    }


# --------------------------------------------------------------------------- #
# Milestone 4 — Temporal Engine, EDA/Findings e Adversarial Auditor (§18-42)
# --------------------------------------------------------------------------- #
@app.get("/datasets/{dataset_id}/temporal/quality")
def temporal_quality(dataset_id: str, mode: str = "strict") -> dict:
    """Qualidade temporal dos timestamps (§18-19). Não valida o relógio (P6)."""
    _require_dataset(dataset_id)
    import json as _json

    with connect() as conn:
        rows = conn.execute(
            "SELECT original_payload FROM raw_records WHERE dataset_id = ?", (dataset_id,)
        ).fetchall()
    parses = [temporal.parse(_json.loads(r["original_payload"]).get("timestamp"), mode)
              for r in rows]
    return {
        "dataset_id": dataset_id,
        "mode": mode,
        "quality_distribution": temporal.quality_summary(parses),
        "samples": [temporal.as_dict(p) for p in parses[:10]],
        "guardrail": ("Conversão de representação realizada. Isso não demonstra que "
                      "o relógio de origem estava sincronizado (§18, P6)."),
    }


@app.get("/datasets/{dataset_id}/eda/hours")
def eda_hours(dataset_id: str, mode: str = "strict") -> dict:
    """Histograma de hora-do-dia (§28) sob um modo de parsing."""
    _require_dataset(dataset_id)
    return eda.hour_distribution(dataset_id, mode)


@app.get("/datasets/{dataset_id}/eda/frequencies")
def eda_frequencies(dataset_id: str, field: str) -> dict:
    _require_dataset(dataset_id)
    return eda.frequencies(dataset_id, field)


@app.get("/datasets/{dataset_id}/eda/outliers")
def eda_outliers(dataset_id: str, field: str = "amount") -> dict:
    """Outliers com Outlier Policy (§30): outlier não é ilicitude."""
    _require_dataset(dataset_id)
    return eda.outliers(dataset_id, field)


@app.post("/datasets/{dataset_id}/eda/detect-temporal-peak")
def eda_detect_peak(dataset_id: str) -> dict:
    """Registra o achado 'concentração 00h-02h' com Pattern Provenance (§32, §89)."""
    _require_dataset(dataset_id)
    return eda.detect_temporal_peak(dataset_id)


@app.get("/datasets/{dataset_id}/eda/pattern-stability")
def eda_stability(dataset_id: str) -> dict:
    """Pattern Stability (§33): recalcula o pico sob naive vs strict."""
    _require_dataset(dataset_id)
    return eda.pattern_stability(dataset_id)


@app.get("/datasets/{dataset_id}/findings")
def get_findings(dataset_id: str) -> dict:
    """Finding Registry (§55, §76). Todos EXPLORATÓRIOS por padrão (§28)."""
    _require_dataset(dataset_id)
    return {"dataset_id": dataset_id, "findings": eda.list_findings(dataset_id)}


@app.post("/datasets/{dataset_id}/findings/{finding_id}/audit")
def audit_finding(dataset_id: str, finding_id: str) -> dict:
    """Adversarial Auditor (§41): 'como isso poderia estar errado?'."""
    _require_dataset(dataset_id)
    try:
        return adversarial.audit_finding(dataset_id, finding_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


class SCSBody(BaseModel):
    hypothesis: str
    support: list[str] = []
    challenge: list[str] = []


@app.post("/adversarial/support-challenge-synthesis")
def scs(body: SCSBody) -> dict:
    """Modo SUPPORT × CHALLENGE × SYNTHESIS (§42)."""
    return adversarial.support_challenge_synthesis(body.hypothesis, body.support, body.challenge)


# --------------------------------------------------------------------------- #
# Milestone 5 — Rollback + Invalidação Automática (§57-59)
# --------------------------------------------------------------------------- #
class RollbackBody(BaseModel):
    actor: str
    justification: str = ""


@app.post("/datasets/{dataset_id}/entities/{entity_id}/finding")
def entity_finding(dataset_id: str, entity_id: str) -> dict:
    """Cria um achado que depende de uma entidade fundida (exemplo §59)."""
    _require_dataset(dataset_id)
    try:
        return eda.entity_aggregate_finding(dataset_id, entity_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/datasets/{dataset_id}/reversible")
def reversible(dataset_id: str) -> dict:
    """Transformações reversíveis do dataset (§57)."""
    _require_dataset(dataset_id)
    return {"dataset_id": dataset_id, "transformations": rollback.list_reversible(dataset_id)}


@app.get("/datasets/{dataset_id}/transformations/{transformation_id}/dependencies")
def dependencies(dataset_id: str, transformation_id: str) -> dict:
    """Dependency Graph de uma transformação (§58)."""
    _require_dataset(dataset_id)
    return rollback.dependency_graph(dataset_id, transformation_id)


@app.post("/datasets/{dataset_id}/transformations/{transformation_id}/rollback")
def do_rollback(dataset_id: str, transformation_id: str, body: RollbackBody) -> dict:
    """Reverte a transformação e invalida dependências (§57-59, P10, P9)."""
    _require_dataset(dataset_id)
    if not body.actor.strip():
        raise HTTPException(422, "Rollback exige identificação do operador (P9).")
    try:
        return rollback.rollback(dataset_id, transformation_id,
                                 actor=body.actor, justification=body.justification)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

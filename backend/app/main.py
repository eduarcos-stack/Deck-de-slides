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

from app.core.db import connect, init_db
from app.modules import ingestion, profiling

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

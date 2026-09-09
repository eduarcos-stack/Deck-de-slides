"""Módulo 1 — Ingestão (Blueprint §10).

Importa localmente CSV/TSV/JSON/JSONL/XLSX, carimba os metadados de
proveniência exigidos (§10), preserva o arquivo bruto no vault (P1) e cria
um RawRecord imutável por linha. NENHUMA transformação de conteúdo ocorre
aqui: os valores são preservados como texto, tal como recebidos.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import polars as pl

from app.core.db import connect
from app.core.hashing import hash_bytes, hash_record
from app.governance import provenance
from app.modules import raw_vault


class IngestionError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_bytes(content: bytes, extension: str) -> list[dict[str, Any]]:
    """Converte o conteúdo bruto em uma lista de registros (dict de strings).

    Todos os valores são lidos como texto para preservar a representação
    original (ex.: zeros à esquerda de CPF, formatos de telefone).
    """
    ext = extension.lower()
    if ext in {".csv", ".tsv"}:
        delimiter = "\t" if ext == ".tsv" else ","
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        return [dict(row) for row in reader]
    if ext == ".jsonl":
        rows = []
        for line in content.decode("utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows
    if ext == ".json":
        data = json.loads(content.decode("utf-8"))
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            raise IngestionError("JSON deve ser objeto ou lista de objetos.")
        return data
    if ext in {".xls", ".xlsx"}:
        try:
            df = pl.read_excel(io.BytesIO(content))
        except Exception as exc:  # noqa: BLE001
            raise IngestionError(
                f"Falha ao ler planilha ({ext}). Engine de Excel indisponível: {exc}"
            ) from exc
        return df.cast(pl.String).to_dicts()
    raise IngestionError(f"Extensão não suportada na ingestão: {extension}")


def ingest(
    *,
    content: bytes,
    filename: str,
    extension: str,
    operator: str,
    case_id: str,
    mime_type: str = "application/octet-stream",
    acquisition_datetime: datetime | None = None,
) -> dict[str, Any]:
    """Executa a ingestão completa de um arquivo (§10).

    Retorna os identificadores criados. Não altera o conteúdo dos dados.
    """
    records = parse_bytes(content, extension)
    if not records:
        raise IngestionError("Arquivo não produziu nenhum registro.")

    file_id = uuid.uuid4().hex
    source_id = uuid.uuid4().hex
    dataset_id = uuid.uuid4().hex
    now = _now()
    file_hash = hash_bytes(content)

    # (P1) preserva o arquivo original, somente-leitura, no vault.
    raw_path = raw_vault.store_raw_file(file_id, content, extension)

    column_names: list[str] = list(records[0].keys())
    row_count = len(records)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sources (
                source_id, file_id, hash, filename, mime_type,
                acquisition_datetime, ingestion_datetime, operator, case_id,
                row_count, column_count, raw_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                file_id,
                file_hash,
                filename,
                mime_type,
                acquisition_datetime.isoformat() if acquisition_datetime else None,
                now.isoformat(),
                operator,
                case_id,
                row_count,
                len(column_names),
                str(raw_path),
            ),
        )
        conn.execute(
            "INSERT INTO datasets (dataset_id, source_id, case_id, version, created_at)"
            " VALUES (?, ?, ?, 'RAW_V1', ?)",
            (dataset_id, source_id, case_id, now.isoformat()),
        )
        for row in records:
            record_id = uuid.uuid4().hex
            payload = {k: (None if v is None else str(v)) for k, v in row.items()}
            conn.execute(
                """
                INSERT INTO raw_records (
                    record_id, dataset_id, source_id, original_payload,
                    hash, ingested_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'OBSERVED')
                """,
                (
                    record_id,
                    dataset_id,
                    source_id,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    hash_record(payload),
                    now.isoformat(),
                ),
            )

    # Provenance Graph (§34): SOURCE -> RAW_RECORDS(dataset)
    provenance.add_edge("SOURCE", source_id, "DATASET", dataset_id, "produced")

    return {
        "source_id": source_id,
        "file_id": file_id,
        "dataset_id": dataset_id,
        "hash": file_hash,
        "row_count": row_count,
        "column_count": len(column_names),
        "columns": column_names,
        "raw_path": str(raw_path),
    }

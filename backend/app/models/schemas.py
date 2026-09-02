"""Contratos de dados do TRACE-LM.

Materializa o Modelo Epistemológico (Blueprint §8) e o Esquema de Dados
Principal (§55). Estes são os objetos formais que o sistema distingue:
Raw Record, Derived Field, Transformation, Entity, Event, Finding.

Regra estrutural (§2, §8, P4): "registro", "entidade" e "evento" são coisas
diferentes e nunca devem ser confundidos silenciosamente.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.status import EpistemicStatus


# --------------------------------------------------------------------------- #
# Fonte e ingestão (Blueprint §10)
# --------------------------------------------------------------------------- #
class SourceMetadata(BaseModel):
    """Metadados de proveniência de um arquivo ingerido (§10)."""

    source_id: str
    file_id: str
    hash: str
    filename: str
    mime_type: str
    acquisition_datetime: Optional[datetime] = None
    ingestion_datetime: datetime
    operator: str
    case_id: str
    row_count: int = 0
    column_count: int = 0


# --------------------------------------------------------------------------- #
# Registro bruto e campo derivado (Blueprint §55, P1/P2)
# --------------------------------------------------------------------------- #
class RawRecord(BaseModel):
    """Registro tal como recebido. Nunca é sobrescrito (P1)."""

    record_id: str
    dataset_id: str
    source_id: str
    original_payload: dict[str, Any]
    hash: str
    ingested_at: datetime
    status: EpistemicStatus = EpistemicStatus.OBSERVED


class DerivedField(BaseModel):
    """Valor derivado, SEMPRE separado do original (P2 — Derived Data Separation).

    Ex.: cpf_raw permanece em RawRecord; cpf_norm vive aqui, ligado à
    transformação que o produziu.
    """

    derived_id: str
    record_id: str
    field_name: str
    raw_value: Optional[str]
    derived_value: Optional[str]
    transformation_id: str
    status: EpistemicStatus = EpistemicStatus.DERIVED


# --------------------------------------------------------------------------- #
# Transformação (Blueprint §35, §55) — o Diário de Transformação
# --------------------------------------------------------------------------- #
class Transformation(BaseModel):
    """Registro de proveniência de UMA transformação (§35).

    Toda transformação relevante gera um destes (P7 — Provenance by Default).
    """

    transformation_id: str
    case_id: str
    dataset_id: str
    rule_id: str
    rule_version: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    actor: str  # "system" | operador humano
    tool: str
    datetime: datetime
    justification: str = ""
    approval: Optional[str] = None  # id/decisão da aprovação humana, quando exigida
    reversible: bool = True
    records_affected: int = 0


# --------------------------------------------------------------------------- #
# Perfilamento (Blueprint §12, §13) — NENHUMA transformação nesta etapa (§13)
# --------------------------------------------------------------------------- #
class ColumnProfile(BaseModel):
    """Perfil de uma coluna (§12)."""

    name: str
    inferred_type: str
    non_null: int
    null_count: int
    empty_count: int
    unique_count: int
    top_values: list[tuple[str, int]] = Field(default_factory=list)
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    detected_formats: dict[str, int] = Field(default_factory=dict)
    missing_sentinels: dict[str, int] = Field(default_factory=dict)
    is_candidate_key: bool = False


class DatasetProfile(BaseModel):
    """Produto do Profiling (§13). Objeto somente-leitura, sem efeitos."""

    dataset_id: str
    row_count: int
    column_count: int
    encoding: str
    columns: list[ColumnProfile]
    candidate_keys: list[str] = Field(default_factory=list)
    exact_duplicate_rows: int = 0
    near_duplicate_pairs: int = 0
    critical_missing_rows: int = 0
    notes: list[str] = Field(default_factory=list)

"""Persistência local em SQLite (Blueprint §11, §35, §55).

Guarda metadados de fonte, registros brutos (payload imutável), o Diário de
Transformação e as arestas do Provenance Graph (§34). O arquivo de banco vive
em disco local (config.DB_PATH) — nada sai da máquina (§47).

O log de transformações é tratado como append-only no nível da aplicação
(§36): a API só insere, nunca atualiza ou apaga linhas do diário.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.core import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id             TEXT PRIMARY KEY,
    file_id               TEXT NOT NULL,
    hash                  TEXT NOT NULL,
    filename              TEXT NOT NULL,
    mime_type             TEXT NOT NULL,
    acquisition_datetime  TEXT,
    ingestion_datetime    TEXT NOT NULL,
    operator              TEXT NOT NULL,
    case_id               TEXT NOT NULL,
    row_count             INTEGER NOT NULL DEFAULT 0,
    column_count          INTEGER NOT NULL DEFAULT 0,
    raw_path              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id   TEXT PRIMARY KEY,
    source_id    TEXT NOT NULL,
    case_id      TEXT NOT NULL,
    version      TEXT NOT NULL DEFAULT 'RAW_V1',
    created_at   TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS raw_records (
    record_id         TEXT PRIMARY KEY,
    dataset_id        TEXT NOT NULL,
    source_id         TEXT NOT NULL,
    original_payload  TEXT NOT NULL,   -- JSON, imutável (P1)
    hash              TEXT NOT NULL,
    ingested_at       TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'OBSERVED',
    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
);

-- Diário de Transformação (§35). Append-only por política de aplicação.
CREATE TABLE IF NOT EXISTS transformations (
    transformation_id  TEXT PRIMARY KEY,
    case_id            TEXT NOT NULL,
    dataset_id         TEXT NOT NULL,
    rule_id            TEXT NOT NULL,
    rule_version       TEXT NOT NULL,
    parameters         TEXT NOT NULL DEFAULT '{}',
    actor              TEXT NOT NULL,
    tool               TEXT NOT NULL,
    datetime           TEXT NOT NULL,
    justification      TEXT NOT NULL DEFAULT '',
    approval           TEXT,
    reversible         INTEGER NOT NULL DEFAULT 1,
    records_affected   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS derived_fields (
    derived_id         TEXT PRIMARY KEY,
    record_id          TEXT NOT NULL,
    field_name         TEXT NOT NULL,
    raw_value          TEXT,
    derived_value      TEXT,
    transformation_id  TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'DERIVED',
    FOREIGN KEY (record_id) REFERENCES raw_records(record_id),
    FOREIGN KEY (transformation_id) REFERENCES transformations(transformation_id)
);

-- Entidade e vínculo (§55). Uma entidade é uma HIPÓTESE de que registros
-- representam a mesma pessoa/empresa/dispositivo (P4 — similaridade ≠ identidade).
CREATE TABLE IF NOT EXISTS entities (
    entity_id    TEXT PRIMARY KEY,
    entity_type  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'CANDIDATE',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_membership (
    membership_id  TEXT PRIMARY KEY,
    record_id      TEXT NOT NULL,
    entity_id      TEXT NOT NULL,
    match_score    REAL,
    decision       TEXT NOT NULL,        -- MATCH | POSSIBLE | NON_MATCH
    decision_actor TEXT NOT NULL,
    evidence       TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL,
    FOREIGN KEY (record_id) REFERENCES raw_records(record_id),
    FOREIGN KEY (entity_id) REFERENCES entities(entity_id)
);

-- Finding (§55): padrão identificado nos dados. Status EXPLORATORY por padrão
-- (§28) — nunca CONCLUSION sem passar pela escada epistemológica (§29).
CREATE TABLE IF NOT EXISTS findings (
    finding_id      TEXT PRIMARY KEY,
    dataset_id      TEXT NOT NULL,
    type            TEXT NOT NULL,
    statement       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'EXPLORATORY_FINDING',
    method          TEXT NOT NULL DEFAULT '{}',   -- parâmetros/decisões metodológicas
    evidence        TEXT NOT NULL DEFAULT '{}',
    confidence      TEXT NOT NULL DEFAULT 'low',
    robust          INTEGER,                       -- NULL até auditar estabilidade
    depends_on      TEXT NOT NULL DEFAULT '[]',    -- dependências explícitas (§58)
    created_at      TEXT NOT NULL
);

-- Segurança (§48): usuários, RBAC, segregação por caso e log de acesso.
CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL,            -- admin | investigator | viewer
    mfa_secret     TEXT,
    mfa_enabled    INTEGER NOT NULL DEFAULT 0,
    disabled       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_access (
    user_id   TEXT NOT NULL,
    case_id   TEXT NOT NULL,
    PRIMARY KEY (user_id, case_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Log de acesso append-only (§48). Só recebe INSERT.
CREATE TABLE IF NOT EXISTS access_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    actor      TEXT,
    role       TEXT,
    method     TEXT NOT NULL,
    path       TEXT NOT NULL,
    status     INTEGER NOT NULL,
    outcome    TEXT NOT NULL,
    at         TEXT NOT NULL
);

-- Provenance Graph (§34): arestas dirigidas entre objetos do sistema.
CREATE TABLE IF NOT EXISTS provenance_edges (
    edge_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    src_type    TEXT NOT NULL,   -- SOURCE | RAW_RECORD | TRANSFORMATION | DERIVED_FIELD | ...
    src_id      TEXT NOT NULL,
    dst_type    TEXT NOT NULL,
    dst_id      TEXT NOT NULL,
    relation    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


# Migrações leves: colunas adicionadas após a primeira versão do schema.
# Mantém bancos locais pré-existentes compatíveis sem apagar dados.
_MIGRATIONS = [
    ("findings", "depends_on", "TEXT NOT NULL DEFAULT '[]'"),
    ("transformations", "reverted_by", "TEXT"),
]


def init_db() -> None:
    """Cria o esquema local se necessário e aplica migrações idempotentes."""
    config.ensure_dirs()
    with connect() as conn:
        conn.executescript(_SCHEMA)
        for table, column, decl in _MIGRATIONS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if column not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Conexão SQLite com row factory e chaves estrangeiras ativadas."""
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

"""Configuração local-first do TRACE-LM (Blueprint §47 — zero exfiltration).

Todos os caminhos são locais. Nada aqui aponta para serviço externo.
"""

from __future__ import annotations

import os
from pathlib import Path

# Raiz do backend (…/backend)
BACKEND_ROOT = Path(__file__).resolve().parents[2]

# Diretório de dados local. Sobreponível por env para testes isolados.
DATA_DIR = Path(os.environ.get("TRACELM_DATA_DIR", BACKEND_ROOT / "data"))

# Vault de dados brutos (somente leitura após escrita) — Blueprint §11.
RAW_VAULT_DIR = DATA_DIR / "raw_vault"

# Banco de metadados / proveniência / diário de transformação.
DB_PATH = DATA_DIR / "trace.db"

# Formatos de ingestão suportados no MVP (Blueprint §10, subconjunto).
SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".json", ".jsonl", ".xls", ".xlsx"}


def ensure_dirs() -> None:
    """Cria a árvore de diretórios local se ainda não existir."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_VAULT_DIR.mkdir(parents=True, exist_ok=True)

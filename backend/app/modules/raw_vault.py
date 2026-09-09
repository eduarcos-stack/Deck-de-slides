"""Raw Data Vault (Blueprint §11, Princípio P1 — Raw Immutability).

O dado bruto é armazenado uma única vez, com hash, e marcado somente-leitura
no sistema de arquivos. Qualquer tentativa de sobrescrever é bloqueada.
Nenhuma análise depende de planilha editável (§11).
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from app.core import config
from app.core.hashing import hash_file


class RawImmutabilityError(RuntimeError):
    """Lançada em qualquer tentativa de alterar um objeto do vault (P1)."""


def store_raw_file(file_id: str, content: bytes, extension: str) -> Path:
    """Grava um arquivo bruto no vault e o torna somente-leitura.

    Recusa-se a sobrescrever um file_id já existente: o raw é imutável (P1).
    """
    config.ensure_dirs()
    dest = config.RAW_VAULT_DIR / f"{file_id}{extension}"
    if dest.exists():
        raise RawImmutabilityError(
            f"Raw já existe para file_id={file_id}. Sobrescrever raw viola P1."
        )
    dest.write_bytes(content)
    # Remove permissão de escrita (dono/grupo/outros) — read-only.
    dest.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return dest


def verify_integrity(path: str | Path, expected_hash: str) -> bool:
    """Confere que o arquivo no vault ainda corresponde ao hash ingerido."""
    return hash_file(path) == expected_hash


def assert_read_only(path: str | Path) -> None:
    """Garante que o arquivo do vault não tem permissão de escrita (P1)."""
    mode = os.stat(path).st_mode
    if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise RawImmutabilityError(f"Arquivo do vault está gravável: {path}")

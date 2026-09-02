"""Integridade e hashing (Blueprint §11, §36).

Todo dado bruto ingerido recebe um hash SHA-256. O hash é o identificador de
integridade que permite detectar qualquer alteração posterior do raw
(Princípio P1 — Raw Immutability).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1024 * 1024  # 1 MiB


def hash_bytes(data: bytes) -> str:
    """SHA-256 de um bloco de bytes, em hexadecimal."""
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | Path) -> str:
    """SHA-256 de um arquivo, lido em blocos (arquivos grandes)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_record(payload: dict[str, Any]) -> str:
    """SHA-256 canônico de um registro (dict).

    A serialização é ordenada por chave para que o mesmo conteúdo produza
    sempre o mesmo hash (base da Reproducibility Rate — §64).
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hash_bytes(canonical.encode("utf-8"))

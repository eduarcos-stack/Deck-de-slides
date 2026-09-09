"""Critério de aceite da Fase 2 (Blueprint §70): nenhum dado raw pode ser alterado.

Testa o Princípio P1 — Raw Immutability (§7).
"""

from __future__ import annotations

import pytest


def test_raw_file_is_read_only(isolated_env):
    from app.modules import raw_vault

    path = raw_vault.store_raw_file("f1", b"conteudo bruto", ".csv")
    # O arquivo gravado não pode ter permissão de escrita.
    raw_vault.assert_read_only(path)  # não deve levantar


def test_cannot_overwrite_raw(isolated_env):
    from app.modules import raw_vault

    raw_vault.store_raw_file("f2", b"original", ".csv")
    with pytest.raises(raw_vault.RawImmutabilityError):
        raw_vault.store_raw_file("f2", b"tentativa de sobrescrever", ".csv")


def test_integrity_hash_detects_tamper(isolated_env):
    from app.core.hashing import hash_bytes
    from app.modules import raw_vault

    content = b"prova pericial"
    path = raw_vault.store_raw_file("f3", content, ".csv")
    assert raw_vault.verify_integrity(path, hash_bytes(content))
    assert not raw_vault.verify_integrity(path, hash_bytes(b"outro"))

"""Fixtures de teste. Isola os dados em diretório temporário (local-first)."""

from __future__ import annotations

import importlib
import os

import pytest


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """Aponta o TRACE-LM para um diretório de dados temporário e limpo."""
    monkeypatch.setenv("TRACELM_DATA_DIR", str(tmp_path / "data"))
    # Recarrega config e db para pegar o novo DATA_DIR.
    from app.core import config, db

    importlib.reload(config)
    importlib.reload(db)
    db.init_db()
    yield tmp_path

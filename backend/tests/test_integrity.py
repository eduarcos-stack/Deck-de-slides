"""Testes do M8 — Integridade da trilha por hash-chain + selo HMAC (§36)."""

from __future__ import annotations

from pathlib import Path

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


def _ingest_and_transform():
    from app.modules import ingestion, normalization

    ds = ingestion.ingest(
        content=DATASET.read_bytes(), filename="im.csv", extension=".csv",
        operator="perito", case_id="CASE-INT",
    )["dataset_id"]
    normalization.apply(ds, "phone", "PHONE_BR_E164_V2", approved_by="ea")
    normalization.apply(ds, "cpf", "CPF_NORMALIZE_V1", approved_by="ea")
    return ds


def test_transformation_chain_is_intact(isolated_env):
    from app.core import integrity
    from app.core.db import connect
    from app.governance.provenance import TRANSFORMATION_CHAIN_FIELDS

    _ingest_and_transform()
    with connect() as conn:
        result = integrity.verify_chain(conn, "transformations", TRANSFORMATION_CHAIN_FIELDS)
    assert result["ok"] is True
    assert result["entries"] >= 2
    assert result["broken_at"] is None


def test_tampering_content_is_detected(isolated_env):
    """Alterar o conteúdo de uma entrada rompe o entry_hash (§36)."""
    from app.core import integrity
    from app.core.db import connect
    from app.governance.provenance import TRANSFORMATION_CHAIN_FIELDS

    _ingest_and_transform()
    with connect() as conn:
        first = conn.execute(
            "SELECT transformation_id FROM transformations ORDER BY rowid LIMIT 1"
        ).fetchone()["transformation_id"]
        # Adulteração: muda records_affected sem recalcular o hash.
        conn.execute(
            "UPDATE transformations SET records_affected = 9999 WHERE transformation_id = ?",
            (first,),
        )
    with connect() as conn:
        result = integrity.verify_chain(conn, "transformations", TRANSFORMATION_CHAIN_FIELDS)
    assert result["ok"] is False
    assert result["broken_at"] == 0


def test_deleting_entry_breaks_chain(isolated_env):
    """Remover uma entrada rompe o encadeamento.

    A FK de derived_fields já protege contra DELETE pela aplicação; aqui
    simulamos um atacante mexendo direto no arquivo SQLite (FKs desligadas) —
    exatamente o cenário que o hash-chain existe para detectar (§36).
    """
    import sqlite3

    from app.core import config, integrity
    from app.core.db import connect
    from app.governance.provenance import TRANSFORMATION_CHAIN_FIELDS

    _ingest_and_transform()
    raw = sqlite3.connect(config.DB_PATH)
    raw.execute("PRAGMA foreign_keys = OFF")
    rowid = raw.execute("SELECT rowid FROM transformations ORDER BY rowid LIMIT 1").fetchone()[0]
    raw.execute("DELETE FROM transformations WHERE rowid = ?", (rowid,))
    raw.commit()
    raw.close()

    with connect() as conn:
        result = integrity.verify_chain(conn, "transformations", TRANSFORMATION_CHAIN_FIELDS)
    assert result["ok"] is False


def test_verify_endpoint_admin_only(isolated_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        atok = c.post("/auth/login", json={"username": "admin", "password": "trace-admin"}).json()["token"]
        ah = {"Authorization": f"Bearer {atok}"}
        # ingestão + transformação via HTTP alimentam as trilhas
        ds = c.post("/ingest", headers=ah,
                    files={"file": ("im.csv", DATASET.read_bytes(), "text/csv")},
                    data={"operator": "admin", "case_id": "CASE-INT2"}).json()["dataset_id"]
        c.post(f"/datasets/{ds}/normalize/apply", headers=ah,
               json={"field": "phone", "rule_id": "PHONE_BR_E164_V2", "approved_by": "admin"})
        res = c.get("/integrity/verify", headers=ah).json()
        assert res["overall_ok"] is True
        assert res["transformation_diary"]["ok"] and res["access_log"]["ok"]

        vtok = c.post("/auth/login", json={"username": "promotor", "password": "trace-viewer"}).json()["token"]
        assert c.get("/integrity/verify", headers={"Authorization": f"Bearer {vtok}"}).status_code == 403

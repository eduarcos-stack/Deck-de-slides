"""Testes do M7 — Segurança (§48): senha, token, MFA, RBAC, segregação, audit."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DATASET = (
    Path(__file__).resolve().parents[2] / "datasets" / "illicit_matrix" / "illicit_matrix.csv"
)


# --------------------------- unitários (núcleo) ---------------------------- #
def test_password_hash_roundtrip():
    from app.core import security

    h = security.hash_password("segredo-forte")
    assert security.verify_password("segredo-forte", h)
    assert not security.verify_password("errado", h)


def test_token_expiry():
    from app.core import security

    good = security.sign_token({"sub": "u1"}, ttl=60)
    assert security.verify_token(good)["sub"] == "u1"
    expired = security.sign_token({"sub": "u1"}, ttl=-1)
    with pytest.raises(security.TokenError):
        security.verify_token(expired)


def test_token_tamper_detected():
    from app.core import security

    tok = security.sign_token({"sub": "u1", "role": "viewer"})
    body, sig = tok.split(".")
    forged = security.sign_token({"sub": "u1", "role": "admin"}).split(".")[0] + "." + sig
    with pytest.raises(security.TokenError):
        security.verify_token(forged)


def test_totp_roundtrip():
    from app.core import security

    secret = security.generate_totp_secret()
    code = security.totp_at(secret)
    assert security.verify_totp(secret, code)
    assert not security.verify_totp(secret, "000000")


# ------------------------------ HTTP / fluxo ------------------------------- #
def _client(isolated_env) -> TestClient:
    from app.main import app

    return TestClient(app)


def _token(client, username, password):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_login_required(isolated_env):
    with _client(isolated_env) as c:
        assert c.get("/auth/me").status_code == 401           # sem token
        assert c.get("/health").status_code == 200            # público


def test_admin_login_and_me(isolated_env):
    with _client(isolated_env) as c:
        tok = _token(c, "admin", "trace-admin")
        me = c.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
        assert me["role"] == "admin"


def test_viewer_is_read_only(isolated_env):
    with _client(isolated_env) as c:
        tok = _token(c, "promotor", "trace-viewer")
        h = {"Authorization": f"Bearer {tok}"}
        # GET permitido
        assert c.get("/rules", headers=h).status_code == 200
        # POST bloqueado (viewer somente leitura)
        r = c.post("/ingest", headers=h,
                   files={"file": ("im.csv", DATASET.read_bytes(), "text/csv")},
                   data={"operator": "x", "case_id": "C1"})
        assert r.status_code == 403


def test_case_segregation(isolated_env):
    with _client(isolated_env) as c:
        # admin cria usuário investigador extra sem acesso ao caso do arcos
        atok = _token(c, "admin", "trace-admin")
        ah = {"Authorization": f"Bearer {atok}"}
        c.post("/auth/users", headers=ah,
               json={"username": "outro", "password": "p", "role": "investigator"})

        # arcos ingere um caso -> ganha acesso
        itok = _token(c, "arcos", "trace-arcos")
        ih = {"Authorization": f"Bearer {itok}"}
        ds = c.post("/ingest", headers=ih,
                    files={"file": ("im.csv", DATASET.read_bytes(), "text/csv")},
                    data={"operator": "arcos", "case_id": "CASE-SEG"}).json()["dataset_id"]
        assert c.get(f"/datasets/{ds}/profile", headers=ih).status_code == 200

        # 'outro' não tem acesso ao caso -> 403
        otok = _token(c, "outro", "p")
        oh = {"Authorization": f"Bearer {otok}"}
        assert c.get(f"/datasets/{ds}/profile", headers=oh).status_code == 403

        # admin ignora a segregação
        assert c.get(f"/datasets/{ds}/profile", headers=ah).status_code == 200


def test_mfa_flow(isolated_env):
    from app.core import security

    with _client(isolated_env) as c:
        tok = _token(c, "arcos", "trace-arcos")
        h = {"Authorization": f"Bearer {tok}"}
        secret = c.post("/auth/mfa/setup", headers=h).json()["secret"]
        code = security.totp_at(secret)
        assert c.post("/auth/mfa/enable", headers=h, json={"code": code}).json()["mfa_enabled"]

        # Agora o login exige segundo fator.
        step1 = c.post("/auth/login", json={"username": "arcos", "password": "trace-arcos"}).json()
        assert step1["mfa_required"] is True
        step2 = c.post("/auth/login/mfa",
                       json={"mfa_token": step1["mfa_token"], "code": security.totp_at(secret)})
        assert step2.status_code == 200 and "token" in step2.json()


def test_access_log_records_and_is_admin_only(isolated_env):
    with _client(isolated_env) as c:
        atok = _token(c, "admin", "trace-admin")
        ah = {"Authorization": f"Bearer {atok}"}
        c.get("/rules", headers=ah)
        log = c.get("/auth/access-log", headers=ah).json()["entries"]
        assert any(e["path"] == "/rules" for e in log)

        vtok = _token(c, "promotor", "trace-viewer")
        vh = {"Authorization": f"Bearer {vtok}"}
        assert c.get("/auth/access-log", headers=vh).status_code == 403

"""Testes da ponte Supabase → TRACE-LM (deploy Grau B, §48).

Gera JWTs HS256 com um segredo conhecido (sem projeto Supabase real) para
validar verificação, expiração, mapeamento de papéis e a troca por sessão.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


SECRET = "test-supabase-jwt-secret"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_jwt(claims: dict, secret: str = SECRET, alg: str = "HS256") -> str:
    header = _b64url(json.dumps({"alg": alg, "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url(sig)}"


def _claims(**over) -> dict:
    base = {"sub": "user-uuid-1", "email": "cidadao@example.com",
            "exp": int(time.time()) + 3600}
    base.update(over)
    return base


def test_disabled_without_secret(isolated_env, monkeypatch):
    from app.modules import supabase_auth

    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    assert supabase_auth.is_enabled() is False


def test_verify_and_default_role_is_viewer(isolated_env, monkeypatch):
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    out = supabase_auth.exchange(_make_jwt(_claims()))
    assert out["user"]["role"] == "viewer"          # menor privilégio (§48)
    assert out["user"]["idp"] == "supabase"
    assert out["token"]


def test_rejects_bad_signature(isolated_env, monkeypatch):
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    forged = _make_jwt(_claims(), secret="wrong-secret")
    try:
        supabase_auth.verify_jwt(forged)
        assert False, "assinatura forjada deveria falhar"
    except supabase_auth.SupabaseAuthError as exc:
        assert "assinatura" in str(exc)


def test_rejects_expired(isolated_env, monkeypatch):
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    try:
        supabase_auth.verify_jwt(_make_jwt(_claims(exp=int(time.time()) - 10)))
        assert False, "token expirado deveria falhar"
    except supabase_auth.SupabaseAuthError as exc:
        assert "expirado" in str(exc)


def test_allowlist_promotes_investigator(isolated_env, monkeypatch):
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    monkeypatch.setenv("TRACELM_SUPABASE_INVESTIGATORS", "arcos@pc.es.gov.br, outro@x.com")
    out = supabase_auth.exchange(_make_jwt(_claims(email="arcos@pc.es.gov.br")))
    assert out["user"]["role"] == "investigator"


def test_explicit_claim_wins(isolated_env, monkeypatch):
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    out = supabase_auth.exchange(
        _make_jwt(_claims(app_metadata={"tracelm_role": "admin"})))
    assert out["user"]["role"] == "admin"


def test_verify_es256_via_jwks(isolated_env, monkeypatch):
    """Token assimétrico (JWT Signing Keys do Supabase) é validado via chave pública."""
    from cryptography.hazmat.primitives.asymmetric import ec
    import jwt as pyjwt
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    priv = ec.generate_private_key(ec.SECP256R1())
    # Injeta a chave pública no lugar do fetch de JWKS (sem rede no teste).
    monkeypatch.setattr(supabase_auth, "_get_signing_key", lambda token: priv.public_key())
    token = pyjwt.encode(_claims(email="perito@pc.es.gov.br"), priv, algorithm="ES256")

    out = supabase_auth.exchange(token)
    assert out["user"]["idp"] == "supabase"
    assert out["user"]["role"] == "viewer"


def test_es256_rejects_wrong_key(isolated_env, monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ec
    import jwt as pyjwt
    from app.modules import supabase_auth

    monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
    signer = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(supabase_auth, "_get_signing_key", lambda token: other.public_key())
    token = pyjwt.encode(_claims(), signer, algorithm="ES256")
    try:
        supabase_auth.verify_jwt(token)
        assert False, "assinatura de chave errada deveria falhar"
    except supabase_auth.SupabaseAuthError:
        pass


def test_session_token_is_accepted_by_middleware(isolated_env, monkeypatch):
    """A sessão emitida pela ponte autentica nas rotas protegidas (§48)."""
    from fastapi.testclient import TestClient
    from app.modules import supabase_auth
    from app.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)
    out = supabase_auth.exchange(_make_jwt(_claims()))
    client = TestClient(app)
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {out['token']}"})
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"

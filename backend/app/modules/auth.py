"""Autenticação, RBAC e segregação por caso (Blueprint §48).

Papéis (RBAC):
  - admin        — acesso total, gestão de usuários, vê todos os casos.
  - investigator — ingere, transforma, decide, reverte e exporta nos seus casos.
  - viewer       — somente leitura.

MFA opcional por usuário (TOTP). Segregação por caso via tabela case_access;
admin ignora a segregação. Nada aqui depende de serviço externo (§47).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from app.core import security
from app.core.db import connect

ROLES = ("admin", "investigator", "viewer")
WRITE_ROLES = ("admin", "investigator")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_users() -> None:
    """Cria o admin padrão e usuários de exemplo, se ainda não existirem."""
    with connect() as conn:
        existing = {r["username"] for r in conn.execute("SELECT username FROM users")}
    defaults = [
        (os.environ.get("TRACELM_ADMIN_USER", "admin"),
         os.environ.get("TRACELM_ADMIN_PASSWORD", "trace-admin"), "admin"),
        ("arcos", os.environ.get("TRACELM_INVESTIGATOR_PASSWORD", "trace-arcos"), "investigator"),
        ("promotor", os.environ.get("TRACELM_VIEWER_PASSWORD", "trace-viewer"), "viewer"),
    ]
    for username, password, role in defaults:
        if username not in existing:
            create_user(username, password, role)


def create_user(username: str, password: str, role: str) -> dict:
    if role not in ROLES:
        raise ValueError(f"papel inválido: {role}")
    user_id = uuid.uuid4().hex
    with connect() as conn:
        conn.execute(
            """INSERT INTO users (user_id, username, password_hash, role, created_at)
               VALUES (?,?,?,?,?)""",
            (user_id, username, security.hash_password(password), role, _now()),
        )
    return {"user_id": user_id, "username": username, "role": role}


def get_user_by_username(username: str) -> dict | None:
    with connect() as conn:
        r = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(r) if r else None


def get_user(user_id: str) -> dict | None:
    with connect() as conn:
        r = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(r) if r else None


def authenticate(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if not user or user["disabled"]:
        return None
    if not security.verify_password(password, user["password_hash"]):
        return None
    return user


def login(username: str, password: str) -> dict:
    """Passo 1 do login. Se o usuário tem MFA, exige o segundo fator."""
    user = authenticate(username, password)
    if not user:
        raise PermissionError("credenciais inválidas")
    if user["mfa_enabled"]:
        # Token curto que apenas atesta 'senha verificada' — não dá acesso.
        challenge = security.sign_token(
            {"sub": user["user_id"], "stage": "mfa"}, ttl=300)
        return {"mfa_required": True, "mfa_token": challenge}
    return {"mfa_required": False, "token": _session_token(user),
            "user": _public(user)}


def login_mfa(mfa_token: str, code: str) -> dict:
    """Passo 2 do login: valida o TOTP e emite o token de sessão."""
    payload = security.verify_token(mfa_token)
    if payload.get("stage") != "mfa":
        raise PermissionError("token de MFA inválido")
    user = get_user(payload["sub"])
    if not user or not user["mfa_enabled"]:
        raise PermissionError("MFA não configurado")
    if not security.verify_totp(user["mfa_secret"], code):
        raise PermissionError("código MFA inválido")
    return {"token": _session_token(user), "user": _public(user)}


def _session_token(user: dict) -> str:
    return security.sign_token({"sub": user["user_id"], "role": user["role"],
                                "username": user["username"]})


def _public(user: dict) -> dict:
    return {"user_id": user["user_id"], "username": user["username"],
            "role": user["role"], "mfa_enabled": bool(user["mfa_enabled"])}


# --------------------------------------------------------------------------- #
# MFA
# --------------------------------------------------------------------------- #
def mfa_setup(user_id: str) -> dict:
    """Gera um segredo TOTP (ainda não ativado) e a URI de provisionamento."""
    user = get_user(user_id)
    if not user:
        raise KeyError("usuário inexistente")
    secret = security.generate_totp_secret()
    with connect() as conn:
        conn.execute("UPDATE users SET mfa_secret = ?, mfa_enabled = 0 WHERE user_id = ?",
                     (secret, user_id))
    return {"secret": secret, "otpauth_uri": security.provisioning_uri(user["username"], secret)}


def mfa_enable(user_id: str, code: str) -> dict:
    """Confirma o TOTP e ativa o MFA para o usuário."""
    user = get_user(user_id)
    if not user or not user["mfa_secret"]:
        raise PermissionError("MFA não iniciado")
    if not security.verify_totp(user["mfa_secret"], code):
        raise PermissionError("código inválido")
    with connect() as conn:
        conn.execute("UPDATE users SET mfa_enabled = 1 WHERE user_id = ?", (user_id,))
    return {"mfa_enabled": True}


# --------------------------------------------------------------------------- #
# Segregação por caso (§48)
# --------------------------------------------------------------------------- #
def grant_case_access(user_id: str, case_id: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO case_access (user_id, case_id) VALUES (?,?)",
                     (user_id, case_id))


def has_case_access(user: dict, case_id: str) -> bool:
    if user["role"] == "admin":
        return True
    with connect() as conn:
        r = conn.execute("SELECT 1 FROM case_access WHERE user_id = ? AND case_id = ?",
                         (user["user_id"], case_id)).fetchone()
    return r is not None


def accessible_cases(user: dict) -> list[str] | None:
    """Casos que o usuário pode ver. None = todos (admin)."""
    if user["role"] == "admin":
        return None
    with connect() as conn:
        rows = conn.execute("SELECT case_id FROM case_access WHERE user_id = ?",
                            (user["user_id"],)).fetchall()
    return [r["case_id"] for r in rows]


def list_users() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT user_id, username, role, mfa_enabled, disabled FROM users ORDER BY username"
        ).fetchall()
    return [dict(r) for r in rows]


def case_of_dataset(dataset_id: str) -> str | None:
    with connect() as conn:
        r = conn.execute("SELECT case_id FROM datasets WHERE dataset_id = ?",
                         (dataset_id,)).fetchone()
    return r["case_id"] if r else None

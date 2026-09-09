"""Ponte de autenticação Supabase → TRACE-LM (deploy Grau B, §48).

O **Supabase Auth** cuida da IDENTIDADE: o login por e-mail/senha acontece no
frontend, via SDK do Supabase. O **FastAPI continua sendo a AUTORIDADE de
autorização**: valida o JWT emitido pelo Supabase, mapeia o usuário para um
papel RBAC (§48) e emite o token de sessão TRACE-LM (HMAC) que todo o resto do
sistema já entende. Assim as 14 capacidades, o RBAC, a segregação por caso e o
audit log (§36) continuam idênticos — só a porta de entrada muda.

A verificação do JWT é feita apenas com a biblioteca padrão (HS256), fiel ao
espírito §47: nenhuma dependência nova, nenhuma chamada de rede para validar o
token. Requer o *legacy JWT secret* do projeto Supabase em `SUPABASE_JWT_SECRET`
(Project Settings → API → JWT Settings, algoritmo HS256).

Se `SUPABASE_JWT_SECRET` não estiver definido, a ponte fica desligada e o
sistema opera só com o login clássico (§48) — é o modo local-first padrão.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone

from app.core import security
from app.core.db import connect
from app.modules import auth


class SupabaseAuthError(Exception):
    """Falha ao validar/trocar o JWT do Supabase."""


def is_enabled() -> bool:
    """A ponte só está ativa quando o segredo do projeto está configurado."""
    return bool(os.environ.get("SUPABASE_JWT_SECRET"))


def demo_case() -> str:
    """Caso ao qual os usuários do Supabase recebem acesso no demo (§48)."""
    return os.environ.get("TRACELM_DEMO_CASE", "CASE-DEMO")


# --------------------------------------------------------------------------- #
# Verificação do JWT (HS256, stdlib) — §47
# --------------------------------------------------------------------------- #
def _b64url_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def verify_jwt(token: str) -> dict:
    """Valida assinatura HS256 e expiração; devolve os claims decodificados."""
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise SupabaseAuthError("SUPABASE_JWT_SECRET não configurado")
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise SupabaseAuthError("JWT malformado") from exc

    try:
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(sig_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise SupabaseAuthError("JWT ilegível") from exc

    if header.get("alg") != "HS256":
        raise SupabaseAuthError(f"algoritmo não suportado: {header.get('alg')}")

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise SupabaseAuthError("assinatura inválida")

    exp = claims.get("exp")
    if exp is not None and time.time() > float(exp):
        raise SupabaseAuthError("token expirado")
    return claims


# --------------------------------------------------------------------------- #
# Mapeamento identidade → papel RBAC (§48, menor privilégio)
# --------------------------------------------------------------------------- #
def _emails(var: str) -> set[str]:
    return {e.strip().lower() for e in os.environ.get(var, "").split(",") if e.strip()}


def _role_for(email: str, claims: dict) -> str:
    """Precedência: claim explícito → allowlists por env → viewer (padrão seguro).

    O papel nunca é inferido de forma silenciosa para algo privilegiado (P8):
    sem allowlist e sem claim, o usuário entra como `viewer` (somente leitura).
    """
    explicit = (claims.get("app_metadata") or {}).get("tracelm_role")
    if explicit in auth.ROLES:
        return explicit
    email = (email or "").lower()
    if email in _emails("TRACELM_SUPABASE_ADMINS"):
        return "admin"
    if email in _emails("TRACELM_SUPABASE_INVESTIGATORS"):
        return "investigator"
    return "viewer"


def _upsert_user(user_id: str, username: str, role: str) -> dict:
    """Espelha o usuário do Supabase na tabela `users` (id estável = `sub`).

    A senha é inutilizável: o login desses usuários vem sempre do Supabase,
    nunca de `/auth/login`. Isso mantém middleware, segregação e audit intactos.
    """
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            unusable = security.hash_password(uuid.uuid4().hex)
            conn.execute(
                """INSERT INTO users (user_id, username, password_hash, role, created_at)
                   VALUES (?,?,?,?,?)""",
                (user_id, username, unusable, role, now),
            )
        elif row["role"] != role or row["username"] != username:
            conn.execute("UPDATE users SET role = ?, username = ? WHERE user_id = ?",
                         (role, username, user_id))
    return {"user_id": user_id, "username": username, "role": role}


def exchange(access_token: str) -> dict:
    """Troca um JWT válido do Supabase por uma sessão TRACE-LM.

    Devolve `{token, user}` no mesmo formato de `auth.login`, para o frontend
    reaproveitar o fluxo de sessão existente sem ramificações.
    """
    claims = verify_jwt(access_token)
    sub = claims.get("sub")
    if not sub:
        raise SupabaseAuthError("JWT sem 'sub'")
    email = claims.get("email") or (claims.get("user_metadata") or {}).get("email") or ""
    role = _role_for(email, claims)
    username = email or f"supabase:{sub[:8]}"
    user = _upsert_user(sub, username, role)

    # Segregação por caso (§48): no demo, todo usuário autenticado enxerga o
    # caso sintético. Admin ignora a segregação por definição.
    if role != "admin":
        auth.grant_case_access(user["user_id"], demo_case())

    token = security.sign_token(
        {"sub": user["user_id"], "role": user["role"],
         "username": user["username"], "idp": "supabase"})
    return {"token": token, "user": {
        "user_id": user["user_id"], "username": user["username"],
        "role": user["role"], "mfa_enabled": False, "idp": "supabase"}}

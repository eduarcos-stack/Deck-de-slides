"""Middleware de segurança (Blueprint §48).

Impõe, em TODAS as rotas exceto uma allowlist mínima:
  1. autenticação por token de sessão (login obrigatório);
  2. RBAC — viewer é somente leitura; gestão de usuários é exclusiva do admin;
  3. segregação por caso — usuário só acessa casos aos quais tem acesso;
  4. log de acesso append-only de cada requisição.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core import security
from app.core.db import connect
from app.modules import auth

# Rotas públicas (sem token).
_PUBLIC = {"/health", "/auth/login", "/auth/login/mfa",
           "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_DATASET_RE = re.compile(r"/datasets/([^/]+)")
_CASE_RE = re.compile(r"/cases/([^/]+)")


def _deny(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        method = request.method

        if method == "OPTIONS" or path in _PUBLIC:
            return await call_next(request)

        # 1. Autenticação.
        authz = request.headers.get("authorization", "")
        token = authz[7:] if authz.lower().startswith("bearer ") else None
        if not token:
            return self._log_and_return(None, method, path, _deny(401, "autenticação exigida"))
        try:
            payload = security.verify_token(token)
        except security.TokenError as exc:
            return self._log_and_return(None, method, path, _deny(401, str(exc)))
        if payload.get("stage") == "mfa":
            return self._log_and_return(None, method, path,
                                        _deny(401, "conclua o MFA para obter sessão"))
        user = auth.get_user(payload.get("sub", ""))
        if not user or user["disabled"]:
            return self._log_and_return(None, method, path, _deny(401, "usuário inválido"))
        request.state.user = user

        # 2. RBAC.
        is_write = method in _WRITE_METHODS
        if path.startswith("/auth/users") or path.startswith("/auth/access-log"):
            if user["role"] != "admin":
                return self._log_and_return(user, method, path,
                                            _deny(403, "recurso exclusivo do admin"))
        elif is_write and not path.startswith("/auth/"):
            if user["role"] not in auth.WRITE_ROLES:
                return self._log_and_return(user, method, path,
                                            _deny(403, "papel viewer é somente leitura"))

        # 3. Segregação por caso.
        case_id = None
        m = _CASE_RE.search(path)
        if m:
            case_id = m.group(1)
        else:
            md = _DATASET_RE.search(path)
            if md:
                case_id = auth.case_of_dataset(md.group(1))
        if case_id and not auth.has_case_access(user, case_id):
            return self._log_and_return(user, method, path,
                                        _deny(403, "sem acesso a este caso (segregação §48)"))

        response = await call_next(request)
        return self._log_and_return(user, method, path, response)

    def _log_and_return(self, user, method, path, response):
        try:
            with connect() as conn:
                conn.execute(
                    """INSERT INTO access_log (actor, role, method, path, status, outcome, at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (user["username"] if user else None,
                     user["role"] if user else None, method, path,
                     response.status_code,
                     "allowed" if response.status_code < 400 else "denied",
                     datetime.now(timezone.utc).isoformat()),
                )
        except Exception:  # noqa: BLE001 — auditoria nunca deve derrubar a resposta
            pass
        return response

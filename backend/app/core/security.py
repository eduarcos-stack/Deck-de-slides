"""Núcleo de segurança (Blueprint §48).

Implementa, apenas com a biblioteca-padrão (sem dependências externas):
  - hashing de senha com scrypt;
  - tokens de sessão assinados com HMAC-SHA256 e expiração (session timeout);
  - TOTP (RFC 6238) para MFA;
  - gestão do segredo de assinatura (env ou arquivo local com permissão restrita).

Local-first (§47): o segredo nunca sai da máquina.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from pathlib import Path

from app.core import config

# Timeout de sessão padrão (§48): 8 horas. Sobreponível por env.
SESSION_TTL_SECONDS = int(os.environ.get("TRACELM_SESSION_TTL", 8 * 3600))


# --------------------------------------------------------------------------- #
# Segredo de assinatura (gestão de secrets, §48)
# --------------------------------------------------------------------------- #
def get_signing_secret() -> bytes:
    """Segredo HMAC. Preferência: env TRACELM_SECRET; senão arquivo local 0600."""
    env = os.environ.get("TRACELM_SECRET")
    if env:
        return env.encode("utf-8")
    config.ensure_dirs()
    secret_path = config.DATA_DIR / ".signing_secret"
    if secret_path.exists():
        return secret_path.read_bytes()
    secret = os.urandom(32)
    secret_path.write_bytes(secret)
    try:
        secret_path.chmod(0o600)
    except OSError:
        pass
    return secret


# --------------------------------------------------------------------------- #
# Senhas (scrypt)
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex),
                            n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, AttributeError):
        return False


# --------------------------------------------------------------------------- #
# Tokens de sessão (HMAC-SHA256 + exp)
# --------------------------------------------------------------------------- #
def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_token(payload: dict, ttl: int | None = None) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + (ttl if ttl is not None else SESSION_TTL_SECONDS)
    raw = _b64u(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64u(hmac.new(get_signing_secret(), raw.encode("ascii"), hashlib.sha256).digest())
    return f"{raw}.{sig}"


class TokenError(Exception):
    pass


def verify_token(token: str) -> dict:
    try:
        raw, sig = token.split(".")
    except ValueError as exc:
        raise TokenError("formato de token inválido") from exc
    expected = _b64u(hmac.new(get_signing_secret(), raw.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise TokenError("assinatura inválida")
    payload = json.loads(_b64u_decode(raw))
    if payload.get("exp", 0) < int(time.time()):
        raise TokenError("sessão expirada")  # session timeout (§48)
    return payload


# --------------------------------------------------------------------------- #
# TOTP / MFA (RFC 6238)
# --------------------------------------------------------------------------- #
def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def totp_at(secret_b32: str, when: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    counter = int((when if when is not None else time.time()) // step)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    """Valida o código considerando uma janela de ±window passos (clock drift)."""
    now = time.time()
    for w in range(-window, window + 1):
        if hmac.compare_digest(totp_at(secret_b32, now + w * 30), str(code).strip()):
            return True
    return False


def provisioning_uri(username: str, secret_b32: str, issuer: str = "TRACE-LM") -> str:
    return (f"otpauth://totp/{issuer}:{username}?secret={secret_b32}"
            f"&issuer={issuer}&algorithm=SHA1&digits=6&period=30")

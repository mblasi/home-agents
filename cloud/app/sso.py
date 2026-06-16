"""Token SSO firmado (HMAC) para autenticar en el backoffice local. FASE 33.22.

La nube actúa de broker: tras el Google sign-in, emite un token corto firmado con
un secreto compartido (`SSO_SECRET`) que el backoffice local verifica. El mismo
codec está duplicado en el backoffice (son deployables separados).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

SSO_SECRET = os.environ.get("SSO_SECRET", "").encode()
DEFAULT_TTL = int(os.environ.get("SSO_TTL", "120"))  # segundos


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def mint(email: str, role: str, ttl: int = DEFAULT_TTL) -> str:
    payload = {"email": email, "role": role, "exp": int(time.time()) + ttl}
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(SSO_SECRET, body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify(token: str) -> dict | None:
    if not SSO_SECRET:
        return None
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(SSO_SECRET, body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:  # noqa: BLE001
        return None

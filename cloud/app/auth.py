"""Autenticación bidireccional. Ver fase33_cloud_backoffice.md (33.4).

- Dashboard (navegador): Firebase ID token, restringido por allow-list de email.
- Bridge (Brain): Google OIDC ID token de la Service Account del bridge, con
  audience = URL del servicio. Sin API keys embebidas.
"""
from __future__ import annotations

import os

from dataclasses import dataclass

from fastapi import Header, HTTPException
from google.auth.transport import requests as ga_requests
from google.oauth2 import id_token as ga_id_token

from . import firestore_db as fdb
from . import rbac

PROJECT_ID = os.environ.get("GCP_PROJECT", "")
FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID", PROJECT_ID)
ALLOWED_EMAILS = {
    e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()
}
BRIDGE_SA_EMAIL = os.environ.get("BRIDGE_SA_EMAIL", "").strip().lower()
SERVICE_URL = os.environ.get("SERVICE_URL", "").strip()  # audience esperado del bridge

_request = ga_requests.Request()


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="falta Authorization: Bearer")
    return authorization.split(" ", 1)[1].strip()


@dataclass
class Principal:
    email: str
    role: str
    caps: dict


def require_dashboard_user(authorization: str | None = Header(default=None)) -> Principal:
    """Valida el Firebase ID token y autoriza contra el roster de usuarios (email→rol)
    pusheado por el Brain. `ALLOWED_EMAILS` queda sólo como bootstrap de emergencia
    (→ admin) para no quedar bloqueado si el roster está vacío. Devuelve el Principal
    con rol y capacidades RBAC (33.20/33.21)."""
    token = _bearer(authorization)
    try:
        claims = ga_id_token.verify_firebase_token(
            token, _request, audience=FIREBASE_PROJECT_ID
        )
    except Exception as exc:  # noqa: BLE001 — token inválido
        raise HTTPException(status_code=401, detail="ID token inválido") from exc
    email = (claims.get("email") or "").lower()
    if not claims.get("email_verified") or not email:
        raise HTTPException(status_code=401, detail="email no verificado")

    role = fdb.get_roster().get(email)
    if role is None and email in ALLOWED_EMAILS:
        role = "admin"  # bootstrap de emergencia
    caps = rbac.caps_for(role)
    if not caps["access"]:
        raise HTTPException(status_code=403, detail="email no autorizado")
    return Principal(email=email, role=role or "", caps=caps)


def require_bridge(authorization: str | None = Header(default=None)) -> str:
    """Valida el OIDC ID token de la SA del bridge. Devuelve el email de la SA."""
    token = _bearer(authorization)
    try:
        claims = ga_id_token.verify_oauth2_token(
            token, _request, audience=SERVICE_URL or None
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="OIDC token inválido") from exc
    email = (claims.get("email") or "").lower()
    if not claims.get("email_verified") or (BRIDGE_SA_EMAIL and email != BRIDGE_SA_EMAIL):
        raise HTTPException(status_code=403, detail="identidad de bridge no autorizada")
    return email

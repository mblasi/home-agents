"""RBAC del backoffice en la nube. FASE 33 (33.21).

Capacidades por rol (consistente con los roles de la gestión de usuarios del core):
  admin       → acceso total: ver todo + emitir comandos admin
  familiar    → read-only completo (ve estado y auditoría, no emite)
  adolescente → read-only vista básica (sin PII de usuarios ni auditoría de comandos)
  niño/invitado/guest/desconocido → SIN acceso al backoffice en la nube
"""
from __future__ import annotations

# access: puede entrar al dashboard | view_full: ve users/auditoría | emit: emite comandos
ROLE_CAPS: dict[str, dict[str, bool]] = {
    "admin":       {"access": True,  "view_full": True,  "emit": True},
    "familiar":    {"access": True,  "view_full": True,  "emit": False},
    "adolescente": {"access": True,  "view_full": False, "emit": False},
}

_NO_ACCESS = {"access": False, "view_full": False, "emit": False}


def caps_for(role: str | None) -> dict[str, bool]:
    return ROLE_CAPS.get(role or "", _NO_ACCESS)


def filter_state(state: dict, caps: dict[str, bool]) -> dict:
    """Aplica RBAC al snapshot que ve el dashboard: oculta PII de usuarios a quien
    no tiene view_full."""
    if caps.get("view_full"):
        return state
    redacted = dict(state)
    redacted["users_summary"] = []  # adolescente no ve la lista de usuarios
    return redacted

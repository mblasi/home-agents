"""RBAC del backoffice en la nube. FASE 33 (33.21).

Capacidades por rol (consistente con los roles de la gestión de usuarios del core):
  admin       → acceso total: ver todo + emitir comandos admin
  familiar    → read-only completo (ve estado y auditoría, no emite)
  adolescente → read-only vista básica (sin PII de usuarios ni auditoría de comandos)
  niño/invitado/guest/desconocido → SIN acceso al backoffice en la nube
"""
from __future__ import annotations

# Capacidades:
#   access    → puede entrar al dashboard
#   view_full → ve roster de usuarios, auditoría y detalle operativo de métricas
#   view_pii  → ve CONTENIDO sensible (texto de comandos/conversaciones); admin-only (FASE 37.2),
#               estrictamente más restrictiva que view_full. Sin ella se ven sólo conteos.
#   emit      → emite comandos admin
ROLE_CAPS: dict[str, dict[str, bool]] = {
    "admin":       {"access": True,  "view_full": True,  "view_pii": True,  "emit": True},
    "familiar":    {"access": True,  "view_full": True,  "view_pii": False, "emit": False},
    "adolescente": {"access": True,  "view_full": False, "view_pii": False, "emit": False},
}

_NO_ACCESS = {"access": False, "view_full": False, "view_pii": False, "emit": False}


def caps_for(role: str | None) -> dict[str, bool]:
    return ROLE_CAPS.get(role or "", _NO_ACCESS)


def filter_state(state: dict, caps: dict[str, bool]) -> dict:
    """Aplica RBAC al snapshot que ve el dashboard.

    Dos niveles de redacción (FASE 37.2):
      - sin `view_full`: oculta el roster de usuarios (PII de identidad).
      - sin `view_pii`: oculta el CONTENIDO de la actividad (el texto de cada comando en
        `recent_commands`) dejando la metadata (ts/agente/ok/latencia). Los `counts` —que son
        sólo enteros— se conservan siempre: el detalle queda detrás de view_pii, los conteos no.
    """
    redacted = dict(state)
    if not caps.get("view_full"):
        redacted["users_summary"] = []  # adolescente no ve la lista de usuarios
    if not caps.get("view_pii"):
        redacted["recent_commands"] = [
            {**c, "text": ""} for c in redacted.get("recent_commands", [])
        ]
    return redacted


def filter_metrics(metrics: dict, caps: dict[str, bool]) -> dict:
    """RBAC sobre las métricas (35.6): los roles sin view_full ven sólo los resúmenes
    y las series agregadas, no el detalle operativo (por modelo/agente, reentrenamientos)."""
    if caps.get("view_full"):
        return metrics
    basic = dict(metrics)
    for k in ("llm_by_model", "llm_by_agent", "retrains"):
        basic[k] = []
    return basic

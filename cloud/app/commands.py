"""Catálogo TIPADO de comandos admin (allow-list cerrada).

Fuente de verdad compartida entre la nube (valida la emisión) y el bridge del Brain
(ejecuta). NUNCA shell arbitrario: un `type` fuera de este catálogo se rechaza sin
ejecutar; parámetros fuera del esquema se rechazan.

Ver masterplan/fase33_cloud_backoffice.md (33.3).
"""
from __future__ import annotations

import re
from typing import Any, Callable

SERVICES = ("capitan-core", "capitan-backoffice", "capitan-wa", "capitan-ear")
CONFIG_TARGETS = ("core", "backoffice")
# Estados de agente que admite el core (PATCH /agents/{id}/status). FASE 37.2.
AGENT_STATUSES = ("active", "planned", "unavailable")
# Componentes del motor de deploy (FASE 34). Nombres lógicos del motor (deploy_engine.SERVICES),
# distintos de las units de SERVICES de arriba.
DEPLOY_SERVICES = ("core", "ear", "backoffice", "wa", "bridge")
# Targets de Cloud Run desplegables por el Brain (driver cloudrun, T4).
CLOUDRUN_SERVICES = ("cloud-bo",)
# Un ref git seguro: sha/tag/branch. Alfanumérico + . _ / - (sin espacios ni metacaracteres de
# shell). El motor igual usa subprocess con lista de args (sin shell), esto es defensa en capas.
_REF_RE = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")


class CommandError(ValueError):
    """Comando o parámetros inválidos contra el catálogo."""


def _enum(name: str, allowed: tuple[str, ...]) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if v not in allowed:
            raise CommandError(f"{name!r} debe ser uno de {allowed}, no {v!r}")
        return v
    return check


def _bool(name: str) -> Callable[[Any], bool]:
    def check(v: Any) -> bool:
        if not isinstance(v, bool):
            raise CommandError(f"{name!r} debe ser bool, no {type(v).__name__}")
        return v
    return check


def _int_range(name: str, lo: int, hi: int) -> Callable[[Any], int]:
    def check(v: Any) -> int:
        if not isinstance(v, int) or isinstance(v, bool) or not (lo <= v <= hi):
            raise CommandError(f"{name!r} debe ser int en [{lo},{hi}], no {v!r}")
        return v
    return check


def _str(name: str) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            raise CommandError(f"{name!r} debe ser str no vacío")
        return v
    return check


def _git_ref(name: str) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if not isinstance(v, str) or not _REF_RE.match(v):
            raise CommandError(f"{name!r} debe ser un ref git válido (sha/tag/branch), no {v!r}")
        return v
    return check


def _str_list(name: str, allowed: tuple[str, ...]) -> Callable[[Any], list[str]]:
    def check(v: Any) -> list[str]:
        if not isinstance(v, list) or not v:
            raise CommandError(f"{name!r} debe ser una lista no vacía")
        for item in v:
            if item not in allowed:
                raise CommandError(f"{name!r}: {item!r} debe ser uno de {allowed}")
        return v
    return check


# type -> { param_name: (validator, required) }
CATALOG: dict[str, dict[str, tuple[Callable[[Any], Any], bool]]] = {
    "service.restart": {"service": (_enum("service", SERVICES), True)},
    "service.status":  {"service": (_enum("service", SERVICES), False)},
    "deploy.run":      {"restart_wa": (_bool("restart_wa"), False)},
    # FASE 34: release con pin de ref por repo. Sin params = todo a HEAD remoto de main
    # (servicios default del motor). `services` acota qué desplegar; *_ref pinea cada repo.
    "deploy.release":  {"services": (_str_list("services", DEPLOY_SERVICES), False),
                        "core_ref": (_git_ref("core_ref"), False),
                        "ear_ref": (_git_ref("ear_ref"), False),
                        "umbrella_ref": (_git_ref("umbrella_ref"), False)},
    # T4: deploy de Cloud Run (cloud-bo) desde el Brain. Sin params = todos los cloudrun targets.
    "deploy.cloud":    {"services": (_str_list("services", CLOUDRUN_SERVICES), False)},
    # 34.16: fuerza el pull de código de un panel (o todos si node_id ausente/'*').
    "deploy.satellites": {"node_id": (_str("node_id"), False)},
    "logs.tail":       {"service": (_enum("service", SERVICES), True),
                        "lines": (_int_range("lines", 1, 500), False)},
    # FASE 37.10: log del satélite de un panel (vía audio_server → ssh a Termux).
    "logs.satellite":  {"node_id": (_str("node_id"), True),
                        "lines": (_int_range("lines", 1, 500), False)},
    "config.reload":   {"target": (_enum("target", CONFIG_TARGETS), True)},
    "wakeword.retrain": {},
    "voice.reenroll":  {"node_id": (_str("node_id"), True),
                        "user_id": (_str("user_id"), True)},
    # FASE 37.2: comandos de operación acotados (sólo admin). El bridge los ejecuta contra
    # APIs/scripts existentes del Brain (37.8). Sin shell arbitrario.
    "agent.toggle":    {"agent_id": (_str("agent_id"), True),
                        "status": (_enum("status", AGENT_STATUSES), True)},
    "panel.reboot":    {"node_id": (_str("node_id"), True)},
    "proactive.run":   {"agent_id": (_str("agent_id"), True)},
    # FASE 38: config por panel (apagado de pantalla por inactividad + dashboard por defecto).
    # El bridge upserta en core y marca el nodo en audio_server; el satélite la reaplica.
    "panel.config":    {"node_id": (_str("node_id"), True),
                        "screen_timeout_secs": (_int_range("screen_timeout_secs", 0, 86400), False),
                        "default_dashboard": (_str("default_dashboard"), False)},
}


def validate_command(cmd_type: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Valida tipo + parámetros contra el catálogo. Devuelve params normalizados.

    Lanza CommandError ante tipo desconocido, parámetro requerido faltante,
    parámetro desconocido, o valor inválido.
    """
    if cmd_type not in CATALOG:
        raise CommandError(f"tipo de comando desconocido: {cmd_type!r}")
    spec = CATALOG[cmd_type]
    params = params or {}

    unknown = set(params) - set(spec)
    if unknown:
        raise CommandError(f"parámetros no permitidos para {cmd_type!r}: {sorted(unknown)}")

    out: dict[str, Any] = {}
    for name, (validator, required) in spec.items():
        if name in params:
            out[name] = validator(params[name])
        elif required:
            raise CommandError(f"falta parámetro requerido {name!r} para {cmd_type!r}")
    return out


# ── Metadata de PRESENTACIÓN (FASE 37.6) ──────────────────────────────────────
# Describe cómo renderizar cada comando/parámetro en una UI final-user (sin JSON crudo):
# label legible, `kind` de widget y restricciones. NO participa de la validación
# (validate_command sigue siendo la única autoridad); es sólo presentación.
#   kind: enum   → dropdown (choices)
#         multi  → checkboxes (choices, lista)
#         bool   → toggle
#         int    → número (min/max)
#         str    → texto libre
#         node   → selector de panel (poblado por el front desde el snapshot)
#         user   → selector de usuario
#         agent  → selector de agente
#         dashboard → selector de dashboard de HA (poblado desde snapshot.dashboards, FASE 38)
# Comandos con entidad-ancla (agent.toggle/panel.reboot/proactive.run/...) se invocan como
# acciones contextuales en su sección; igual se exponen aquí para completitud.
CMD_LABELS: dict[str, str] = {
    "service.restart": "Reiniciar servicio",
    "service.status": "Estado de servicio",
    "deploy.run": "Deploy (legacy)",
    "deploy.release": "Release de servicios",
    "deploy.cloud": "Deploy Cloud Run",
    "deploy.satellites": "Actualizar paneles",
    "logs.tail": "Ver logs de servicio",
    "logs.satellite": "Ver log de un panel",
    "config.reload": "Recargar configuración",
    "wakeword.retrain": "Reentrenar wake word",
    "voice.reenroll": "Re-enrolar voz",
    "agent.toggle": "Cambiar estado de agente",
    "panel.reboot": "Reiniciar panel",
    "proactive.run": "Correr agente proactivo",
    "panel.config": "Configurar panel",
}

PRESENTATION: dict[str, dict[str, dict[str, Any]]] = {
    "service.restart": {"service": {"kind": "enum", "label": "Servicio", "choices": SERVICES}},
    "service.status":  {"service": {"kind": "enum", "label": "Servicio", "choices": SERVICES}},
    "deploy.run":      {"restart_wa": {"kind": "bool", "label": "Reiniciar WhatsApp", "default": False}},
    "deploy.release":  {"services": {"kind": "multi", "label": "Servicios", "choices": DEPLOY_SERVICES},
                        "core_ref": {"kind": "str", "label": "Ref core (sha/tag/branch)"},
                        "ear_ref": {"kind": "str", "label": "Ref ear"},
                        "umbrella_ref": {"kind": "str", "label": "Ref umbrella"}},
    "deploy.cloud":    {"services": {"kind": "multi", "label": "Targets Cloud Run", "choices": CLOUDRUN_SERVICES}},
    "deploy.satellites": {"node_id": {"kind": "node", "label": "Panel (vacío = todos)"}},
    "logs.tail":       {"service": {"kind": "enum", "label": "Servicio", "choices": SERVICES},
                        "lines": {"kind": "int", "label": "Líneas", "min": 1, "max": 500, "default": 100}},
    "logs.satellite":  {"node_id": {"kind": "node", "label": "Panel"},
                        "lines": {"kind": "int", "label": "Líneas", "min": 1, "max": 500, "default": 100}},
    "config.reload":   {"target": {"kind": "enum", "label": "Target", "choices": CONFIG_TARGETS}},
    "wakeword.retrain": {},
    "voice.reenroll":  {"node_id": {"kind": "node", "label": "Panel"},
                        "user_id": {"kind": "user", "label": "Usuario"}},
    "agent.toggle":    {"agent_id": {"kind": "agent", "label": "Agente"},
                        "status": {"kind": "enum", "label": "Estado", "choices": AGENT_STATUSES}},
    "panel.reboot":    {"node_id": {"kind": "node", "label": "Panel"}},
    "proactive.run":   {"agent_id": {"kind": "agent", "label": "Agente"}},
    "panel.config":    {"node_id": {"kind": "node", "label": "Panel"},
                        "screen_timeout_secs": {"kind": "int", "label": "Apagar pantalla tras (seg, 0 = nunca)",
                                                "min": 0, "max": 86400, "default": 120},
                        "default_dashboard": {"kind": "dashboard", "label": "Dashboard por defecto"}},
}


def catalog_summary() -> list[dict[str, Any]]:
    """Resumen del catálogo para el frontend, enriquecido con metadata de presentación (37.6).

    Cada comando lleva un `label` legible y cada parámetro un `kind` de widget + restricciones
    (`choices`/`min`/`max`/`default`). Si un parámetro no tiene presentación declarada, cae a
    `kind=str`. No altera la validación: es sólo para renderizar la UI."""
    out = []
    for t, spec in CATALOG.items():
        pres = PRESENTATION.get(t, {})
        params = []
        for n, (_, req) in spec.items():
            meta = dict(pres.get(n) or {})
            meta.setdefault("kind", "str")
            meta.setdefault("label", n)
            # choices como lista (las constantes son tuplas) para serializar a JSON
            if "choices" in meta:
                meta["choices"] = list(meta["choices"])
            params.append({"name": n, "required": req, **meta})
        out.append({"type": t, "label": CMD_LABELS.get(t, t), "params": params})
    return out

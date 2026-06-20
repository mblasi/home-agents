"""Catálogo TIPADO de comandos admin (allow-list cerrada).

Fuente de verdad compartida entre la nube (valida la emisión) y el bridge del SER9
(ejecuta). NUNCA shell arbitrario: un `type` fuera de este catálogo se rechaza sin
ejecutar; parámetros fuera del esquema se rechazan.

Ver masterplan/fase33_cloud_backoffice.md (33.3).
"""
from __future__ import annotations

import re
from typing import Any, Callable

SERVICES = ("capitan-core", "capitan-backoffice", "capitan-wa", "capitan-ear")
CONFIG_TARGETS = ("core", "backoffice")
# Componentes del motor de deploy (FASE 34). Nombres lógicos del motor (deploy_engine.SERVICES),
# distintos de las units de SERVICES de arriba.
DEPLOY_SERVICES = ("core", "ear", "backoffice", "wa", "bridge")
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
    "logs.tail":       {"service": (_enum("service", SERVICES), True),
                        "lines": (_int_range("lines", 1, 500), False)},
    "config.reload":   {"target": (_enum("target", CONFIG_TARGETS), True)},
    "wakeword.retrain": {},
    "voice.reenroll":  {"node_id": (_str("node_id"), True),
                        "user_id": (_str("user_id"), True)},
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


def catalog_summary() -> list[dict[str, Any]]:
    """Resumen del catálogo para el frontend (qué comandos se pueden emitir)."""
    out = []
    for t, spec in CATALOG.items():
        out.append({
            "type": t,
            "params": [{"name": n, "required": req} for n, (_, req) in spec.items()],
        })
    return out

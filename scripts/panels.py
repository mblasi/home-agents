#!/usr/bin/env python3
"""
Loader/resolver del registro de paneles.

Fuente de verdad: la **base de datos** (tabla `panels`), expuesta por el core en `GET /panels`
(FASE 32 — reemplaza panels.yaml). Resuelve un panel por nombre o ambiente (room) a su config
(IP, node_id, etc.), para que comandos/scripts no hardcodeen IPs.

Uso CLI:
    python scripts/panels.py list
    python scripts/panels.py resolve comedor      # imprime la IP
    python scripts/panels.py resolve comedor ip    # campo específico
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

# Core que sirve el registro de paneles (DB). Default: SER9.
_CORE_URL = os.environ.get("CORE_URL", "http://192.168.68.132:8765")


def load_panels() -> list[dict]:
    """Lista de paneles desde el core (DB). [] si el core no responde."""
    try:
        with urllib.request.urlopen(f"{_CORE_URL}/panels", timeout=5) as r:
            return json.load(r) or []
    except Exception:
        return []


def resolve(key: str) -> dict | None:
    """Resuelve un panel por `name` o `room` (case-insensitive). None si no existe.
    Si `key` parece una IP (tiene puntos y dígitos), devuelve un panel sintético con esa IP
    — así los comandos aceptan tanto nombre como IP cruda."""
    if not key:
        return None
    k = key.strip().lower()
    for p in load_panels():
        if str(p.get("name", "")).lower() == k or str(p.get("room", "")).lower() == k:
            return p
    # fallback: si parece IP, devolver panel mínimo (compat con IP cruda)
    if k.replace(".", "").isdigit() and k.count(".") == 3:
        return {"name": key, "room": key, "ip": key, "node_id": f"nspanel-{key}"}
    return None


def resolve_ip(key: str, default: str = "192.168.68.113") -> str:
    """IP de un panel por nombre/room/IP. Default = comedor."""
    p = resolve(key)
    return p.get("ip", default) if p else default


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "list":
        for p in load_panels():
            print(f"{p.get('name'):12} {p.get('ip'):16} {p.get('node_id'):20} users={p.get('users')}")
    elif args[0] == "resolve" and len(args) >= 2:
        p = resolve(args[1])
        if p is None:
            print("", end="")
            sys.exit(1)
        field = args[2] if len(args) >= 3 else "ip"
        print(p.get(field, ""))
    else:
        print(__doc__)
        sys.exit(1)

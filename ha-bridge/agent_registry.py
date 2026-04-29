#!/usr/bin/env python3
"""
Registro de agentes disponibles y dispatcher de pedidos.

El dispatcher determina qué agente debe manejar un comando.
Solo el agente HAOS está activo; los demás están planificados.
"""

from __future__ import annotations
import json
import os
import time
import requests

# ── Registro de agentes ────────────────────────────────────────────────────────

REGISTRY: dict[str, dict] = {
    "haos": {
        "name":   "Domótica",
        "icon":   "🏠",
        "desc":   "Luces, temperatura, electrodomésticos, riego",
        "status": "active",    # active | planned | unavailable
        "keywords": [
            "luz", "luces", "lampara", "lamparita",
            "aire", "calefaccion", "temperatura",
            "persiana", "toldo", "cortina",
            "tele", "television", "tv",
            "pava", "hervidor", "freidora",
            "agua", "valvula", "riego",
            "garaje", "patio", "puerta",
            "alexa", "echo",
            "prende", "apaga", "abre", "cierra", "sube", "baja",
        ],
    },
    "clima": {
        "name":   "Clima",
        "icon":   "🌤",
        "desc":   "Pronóstico del tiempo y alertas meteorológicas",
        "status": "planned",
        "keywords": [
            "clima", "tiempo", "lluvia", "temperatura exterior",
            "pronostico", "viento", "humedad", "sol",
        ],
    },
    "agenda": {
        "name":   "Agenda",
        "icon":   "📅",
        "desc":   "Calendario, recordatorios y reuniones",
        "status": "planned",
        "keywords": [
            "agenda", "reunion", "recordatorio", "evento",
            "calendario", "turno", "cita", "mañana", "hoy",
        ],
    },
    "inversiones": {
        "name":   "Inversiones",
        "icon":   "📈",
        "desc":   "Portfolio, cotizaciones y mercados",
        "status": "planned",
        "keywords": [
            "acciones", "bolsa", "dolar", "cripto", "bitcoin",
            "portfolio", "inversion", "mercado", "cotizacion",
        ],
    },
    "viajes": {
        "name":   "Viajes",
        "icon":   "✈️",
        "desc":   "Planificación de viajes y reservas",
        "status": "planned",
        "keywords": [
            "vuelo", "hotel", "viaje", "reserva", "pasaje",
            "aerolinea", "destino", "hospedaje",
        ],
    },
}

# ── Dispatcher ─────────────────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "qwen2.5:7b"

_DISPATCH_SYSTEM = """Dado un comando de voz en español, determina qué agente debe manejarlo.
Respondé SOLO con una de estas palabras: haos, clima, agenda, inversiones, viajes, unknown

haos:        control del hogar (luces, temperatura interior, electrodomésticos, riego, persianas)
clima:       tiempo, pronóstico, lluvia, temperatura exterior
agenda:      reuniones, recordatorios, calendario, citas, turnos
inversiones: acciones, cripto, portafolio, cotizaciones, bolsa, dólar
viajes:      vuelos, hoteles, planificación de viajes, reservas
unknown:     nada de lo anterior"""


def dispatch(text: str) -> str:
    """Devuelve el id del agente que debe manejar el texto. Rápido: usa keywords primero."""
    text_lower = text.lower()

    # Paso 1: match rápido por keywords
    scores: dict[str, int] = {}
    for agent_id, info in REGISTRY.items():
        hits = sum(1 for kw in info.get("keywords", []) if kw in text_lower)
        if hits:
            scores[agent_id] = hits
    if scores:
        return max(scores, key=lambda k: scores[k])

    # Paso 2: clasificación con LLM si no hubo keywords
    try:
        r = requests.post(OLLAMA_URL, json={
            "model":   MODEL,
            "system":  _DISPATCH_SYSTEM,
            "prompt":  text,
            "stream":  False,
            "options": {"temperature": 0, "num_predict": 10},
        }, timeout=10)
        agent_id = r.json()["response"].strip().lower().split()[0]
        if agent_id in REGISTRY:
            return agent_id
    except Exception:
        pass

    return "unknown"


def agent_status(agent_id: str) -> str:
    return REGISTRY.get(agent_id, {}).get("status", "unknown")


def unavailable_response(agent_id: str) -> str:
    info = REGISTRY.get(agent_id, {})
    name = info.get("name", agent_id)
    return f"El agente de {name} todavía no está disponible."


# ── Métricas de agentes ────────────────────────────────────────────────────────

METRICS_DIR = "/tmp/capitan"

def write_active_agent(agent_id: str) -> None:
    path = os.path.join(METRICS_DIR, "active_agent.json")
    tmp  = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"agent": agent_id, "ts": time.time()}, f)
    os.replace(tmp, path)

#!/usr/bin/env python3
"""
Convierte texto transcripto en acciones de Home Assistant.
Flujo: texto → qwen2.5:7b (Ollama) → parse ACTION → ha_client.call_service
"""

import re
import sys
import os
import requests

sys.path.insert(0, os.path.dirname(__file__))
import ha_client
import agent_registry as registry

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "qwen2.5:7b"


def _build_entity_lines() -> str:
    seen = {}
    for alias, eid in ha_client.ENTITIES.items():
        seen.setdefault(eid, []).append(alias)
    return "\n".join(f"  {eid}  →  {', '.join(aliases)}" for eid, aliases in seen.items())


SYSTEM_PROMPT = f"""Sos el agente Capitán, controlás una casa inteligente con Home Assistant.
Ante un comando de voz en español, respondé ÚNICAMENTE con una línea en este formato:
ACTION: dominio.servicio | entity_id: entity_id_real

Para parámetros extra (ej: temperatura):
ACTION: climate.set_temperature | entity_id: climate.midea_ac_150633093419021 | temperature: 22

Si el comando no corresponde a ninguna entidad o no es accionable, respondé exactamente:
NONE

No agregues explicaciones, saludos ni texto extra. Solo la línea ACTION o NONE.

Entidades disponibles:
{_build_entity_lines()}

Servicios por dominio:
  light        → turn_on, turn_off, toggle
  switch       → turn_on, turn_off, toggle
  cover        → open_cover, close_cover, stop_cover
  climate      → turn_on, turn_off, set_temperature (param: temperature: N), set_hvac_mode (param: hvac_mode: cool|heat|auto|dry|fan_only)
  media_player → turn_on, turn_off, media_play, media_pause, volume_up, volume_down

Regla importante: el dominio en ACTION debe coincidir con el prefijo del entity_id.
Ejemplo correcto:   ACTION: light.turn_on | entity_id: light.wiz_rgbw_tunable_1fdbc2
Ejemplo incorrecto: ACTION: switch.turn_on | entity_id: light.wiz_rgbw_tunable_1fdbc2

Ejemplos:
  "prende la luz"       → ACTION: light.turn_on | entity_id: light.wiz_rgbw_tunable_1fdbc2
  "apaga la luz"        → ACTION: light.turn_off | entity_id: light.wiz_rgbw_tunable_1fdbc2
  "apaga el aire"       → ACTION: climate.turn_off | entity_id: climate.midea_ac_150633093419021
  "pon el aire a 20"    → ACTION: climate.set_temperature | entity_id: climate.midea_ac_150633093419021 | temperature: 20
  "abre la persiana"    → ACTION: cover.open_cover | entity_id: cover.tze200_nhyj64w2_ts0601
  "apaga la tele"       → ACTION: media_player.turn_off | entity_id: media_player.samsung_q8_65_tv
  "qué hora es"         → NONE
"""

_ACTION_RE = re.compile(
    r"ACTION:\s*(?P<domain>\w+)\.(?P<service>\w+)"
    r"\s*\|\s*entity_id:\s*(?P<entity_id>[\w.]+)"
    r"(?P<extras>(?:\s*\|\s*\w+:\s*\S+)*)"
)

_VERBS = {
    "turn_on":        "encendido",
    "turn_off":       "apagado",
    "toggle":         "alternado",
    "open_cover":     "abierto",
    "close_cover":    "cerrado",
    "stop_cover":     "detenido",
    "set_temperature":"temperatura ajustada",
    "set_hvac_mode":  "modo ajustado",
    "media_play":     "reproduciendo",
    "media_pause":    "pausado",
    "volume_up":      "volumen subido",
    "volume_down":    "volumen bajado",
}


def _ask_llm(command: str) -> str:
    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": command,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 80},
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["response"].strip()


def _parse(raw: str) -> dict | None:
    m = _ACTION_RE.search(raw)
    if not m:
        return None
    extras = {}
    for k, v in re.findall(r"\|\s*(\w+):\s*(\S+)", m.group("extras")):
        try:
            extras[k] = float(v) if "." in v else int(v)
        except ValueError:
            extras[k] = v
    entity_id = m.group("entity_id")
    # El dominio debe coincidir con el prefijo del entity_id
    domain = entity_id.split(".")[0]
    return {
        "domain":    domain,
        "service":   m.group("service"),
        "entity_id": entity_id,
        "extras":    extras,
    }


def process(text: str, source: dict | None = None) -> tuple[str, str | None, str]:
    """
    Procesa texto transcripto.
    Devuelve (texto_respuesta_para_TTS, descripcion_accion_o_None, agent_id).
    """
    # Dispatcher: determinar qué agente debe manejar el pedido
    agent_id = registry.dispatch(text)
    registry.write_active_agent(agent_id)

    # Si el agente no es haos y no está activo, responder apropiadamente
    if agent_id != "haos" and registry.agent_status(agent_id) != "active":
        return registry.unavailable_response(agent_id), None, agent_id

    # Agente HAOS (único activo)
    try:
        raw = _ask_llm(text)
    except requests.exceptions.ConnectionError:
        return "No puedo conectarme al modelo de lenguaje.", None, agent_id
    except Exception as e:
        return f"Error en el modelo: {e}", None, agent_id

    if not raw or raw.strip().upper() == "NONE":
        return "No encontré ninguna acción para ese comando.", None, agent_id

    action = _parse(raw)
    if action is None:
        return "No pude interpretar la respuesta del modelo.", None, agent_id

    try:
        ha_client.call_service(
            action["domain"], action["service"], action["entity_id"], **action["extras"]
        )
    except requests.exceptions.HTTPError as e:
        return f"Error al ejecutar en Home Assistant: {e}", None, agent_id

    verb = _VERBS.get(action["service"], "ejecutado")
    desc = f"{action['domain']}.{action['service']} → {action['entity_id']}"
    return f"Listo, {verb}.", desc, agent_id


if __name__ == "__main__":
    # Test rápido
    test_commands = [
        "prende la luz",
        "apaga el aire",
        "abre la persiana",
        "pon el aire a 22 grados",
        "qué hora es",
    ]
    for cmd in test_commands:
        print(f"\n>>> {cmd}")
        resp, desc = process(cmd)
        print(f"    LLM action: {desc}")
        print(f"    Respuesta:  {resp}")

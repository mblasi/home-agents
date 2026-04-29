#!/usr/bin/env python3
"""
Cliente REST para Home Assistant OS.
Carga credenciales desde .env en la raíz del repo.
"""

import os
import requests

def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    cfg = {}
    try:
        with open(os.path.abspath(env_path)) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return cfg

_cfg = _load_env()
HAOS_URL   = _cfg.get("HAOS_URL",   os.environ.get("HAOS_URL", ""))
HAOS_TOKEN = _cfg.get("HAOS_TOKEN", os.environ.get("HAOS_TOKEN", ""))

_HEADERS = {
    "Authorization": f"Bearer {HAOS_TOKEN}",
    "Content-Type": "application/json",
}


def get_state(entity_id: str) -> dict:
    """Devuelve el estado completo de una entidad."""
    r = requests.get(f"{HAOS_URL}/api/states/{entity_id}", headers=_HEADERS, timeout=5)
    r.raise_for_status()
    return r.json()


def call_service(domain: str, service: str, entity_id: str, **kwargs) -> list:
    """Llama a un servicio de HA. Ej: call_service('light', 'turn_on', 'light.xyz')"""
    payload = {"entity_id": entity_id, **kwargs}
    r = requests.post(
        f"{HAOS_URL}/api/services/{domain}/{service}",
        headers=_HEADERS,
        json=payload,
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


def turn_on(entity_id: str, **kwargs) -> list:
    domain = entity_id.split(".")[0]
    return call_service(domain, "turn_on", entity_id, **kwargs)


def turn_off(entity_id: str, **kwargs) -> list:
    domain = entity_id.split(".")[0]
    return call_service(domain, "turn_off", entity_id, **kwargs)


# ── Mapa de entidades ──────────────────────────────────────────────────────────
# Alias en español → entity_id real en HAOS

ENTITIES = {
    # Iluminación
    "luz":                  "light.wiz_rgbw_tunable_1fdbc2",
    "luz del garaje":       "switch.garaje_light",
    "luz del patio":        "switch.patio_light",
    "luz de la puerta":     "switch.puerta_principal_light",

    # Climatización
    "aire":                 "climate.midea_ac_150633093419021",
    "aire acondicionado":   "climate.midea_ac_150633093419021",

    # Cobertura
    "persiana":             "cover.tze200_nhyj64w2_ts0601",
    "toldo":                "cover.tze200_nhyj64w2_ts0601",

    # Electrodomésticos
    "pava":                 "switch.mi_smart_kettle_pro",
    "hervidor":             "switch.mi_smart_kettle_pro",
    "freidora":             "switch.mi_smart_air_fryer_3_5l",

    # Agua y riego
    "agua":                 "switch.agua_principal_valvula_de_cierre",
    "valvula":              "switch.agua_principal_valvula_de_cierre",
    "riego zona 1":         "switch.zone_1",
    "riego zona 2":         "switch.zone_2",
    "riego zona 3":         "switch.zone_3",
    "riego zona 4":         "switch.zone_4",
    "riego zona 5":         "switch.zone_5",
    "riego zona 6":         "switch.zone_6",
    "riego zona 7":         "switch.zone_7",
    "riego zona 8":         "switch.zone_8",

    # Televisores
    "tele":                 "media_player.samsung_q8_65_tv",
    "television":           "media_player.samsung_q8_65_tv",
    "tv":                   "media_player.samsung_q8_65_tv",
    "tv del cuarto":        "media_player.samsung_7_series_50",

    # Echos
    "alexa":                "media_player.echo_de_matias",
    "echo":                 "media_player.echo_de_matias",
}


if __name__ == "__main__":
    # Test rápido de conexión
    import json
    print(f"HAOS: {HAOS_URL}")
    try:
        r = requests.get(f"{HAOS_URL}/api/", headers=_HEADERS, timeout=5)
        print(f"API status: {r.json()['message']}")

        state = get_state("light.wiz_rgbw_tunable_1fdbc2")
        print(f"Luz WiZ: {state['state']} | atributos: {json.dumps(state.get('attributes', {}), ensure_ascii=False)}")

        state2 = get_state("climate.midea_ac_150633093419021")
        print(f"AC Midea: {state2['state']} | temp={state2['attributes'].get('current_temperature')}°C")
    except Exception as e:
        print(f"Error: {e}")

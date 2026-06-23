"""Construcción del snapshot de estado (Brain → nube). FASE 33 (33.10).

Reusa datos que ya producen core (:8765) y audio_server (:8766) + /tmp/capitan.
Best-effort y resiliente: cada fuente está envuelta en try/except y nunca propaga
excepciones — un snapshot parcial es mejor que ninguno. Allow-list de campos: sólo
se serializa lo definido en el contrato (33.2), nunca objetos de dominio completos.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

CORE_URL = os.environ.get("CORE_URL", "http://localhost:8765")
AUDIO_URL = os.environ.get("AUDIO_SERVER_URL", "http://localhost:8766")
LLM_URL = os.environ.get("LLM_BASE_URL", os.environ.get("OLLAMA_URL", "http://localhost:11434"))
METRICS_DIR = Path(os.environ.get("METRICS_DIR", "/tmp/capitan"))
HOST = os.environ.get("BRIDGE_HOST", "capitan-lxc")
RECENT_LIMIT = int(os.environ.get("SNAPSHOT_RECENT_LIMIT", "20"))

SYSTEMD_UNITS = {
    "core": "capitan-core",
    "backoffice": "capitan-backoffice",
    "wa": "capitan-wa",
}


def _get(url: str, timeout: int = 4):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _systemctl_active(unit: str) -> bool:
    try:
        out = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True, text=True, timeout=4,
        )
        return out.stdout.strip() == "active"
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _services() -> dict:
    core_ok = _get(f"{CORE_URL}/health") is not None
    llm_ok = _get(f"{LLM_URL}/api/tags", timeout=3) is not None
    audio = _get(f"{AUDIO_URL}/health")
    ear_ok = bool(audio) and audio.get("status") == "ok"
    return {
        "core":       {"up": core_ok, "detail": "ok" if core_ok else "down"},
        "llm":        {"up": llm_ok,  "detail": "ok" if llm_ok else "down"},
        "ear":        {"up": ear_ok,  "detail": f"{audio.get('nodes', 0)} nodos" if ear_ok else "down"},
        "backoffice": {"up": _systemctl_active(SYSTEMD_UNITS["backoffice"]), "detail": ""},
        "wa":         {"up": _systemctl_active(SYSTEMD_UNITS["wa"]), "detail": ""},
    }


def _agents() -> list[dict]:
    data = _get(f"{CORE_URL}/agents", timeout=8)
    if not isinstance(data, dict):
        return []
    out = []
    for aid, meta in data.items():
        if not isinstance(meta, dict):
            continue
        kind = meta.get("kind", "domain")
        entry = {
            "id": aid,
            "active": meta.get("status") == "active",
            "proactive": bool(meta.get("proactive") or meta.get("proactive_enabled")),
            "kind": kind,
        }
        # FASE 43: la config efectiva del orquestador viaja para prellenar el form de agent.config.
        # Sin secretos (model/system_prompt/guards). Sólo el orquestador la necesita en la UI.
        if kind == "orchestrator":
            entry["config"] = meta.get("config") or {}
        out.append(entry)
    return out


def _models() -> list[str]:
    """Modelos LLM disponibles en Ollama (FASE 43), para el selector del comando agent.config."""
    data = _get(f"{CORE_URL}/models")
    models = data.get("models") if isinstance(data, dict) else None
    return models if isinstance(models, list) else []


def _nodes() -> list[dict]:
    data = _get(f"{AUDIO_URL}/nodes")
    return data if isinstance(data, list) else []


def _panel_configs() -> dict[str, dict]:
    """Config por panel desde core (FASE 38), indexada por node_id. No PII: sólo
    screen_timeout_secs + default_dashboard."""
    data = _get(f"{CORE_URL}/panels")
    out: dict[str, dict] = {}
    for p in data if isinstance(data, list) else []:
        nid = p.get("node_id")
        if nid:
            out[nid] = p.get("config") or {}
    return out


def _dashboards() -> list[dict]:
    """Dashboards de HA para el selector de 'dashboard por defecto' (FASE 38)."""
    data = _get(f"{CORE_URL}/dashboards")
    return data if isinstance(data, list) else []


def _wakeword(nodes: list[dict]) -> dict:
    fps = [n.get("fp", 0) for n in nodes]
    status = (_get(f"{CORE_URL}/wakeword/train/status") or {}).get("status", "idle")
    configs = _panel_configs()
    return {
        "last_score": None,  # no expuesto por el audio_server actual
        "false_positives_24h": sum(fps) if fps else None,
        "status": status,    # estado del último retrain (FASE 37.1/37.7)
        "nodes": [
            {
                "id": n.get("node_id", n.get("room", "?")),
                "ip": n.get("ip") or None,
                "online": n.get("state") == "active",
                "rms": None,
                "config": configs.get(n.get("node_id"), {}),   # FASE 38: config guardada (core)
                "device_config": n.get("device_config") or {}, # FASE 38: config REAL del dispositivo
            }
            for n in nodes
        ],
    }


def _recent_commands(nodes: list[dict]) -> list[dict]:
    """Sin history.json en el sistema actual: el último comando por nodo es la
    señal disponible (audio_server /nodes)."""
    out = []
    for n in nodes:
        cmd = n.get("last_command")
        if not cmd:
            continue
        ts = n.get("last_command_ts")
        out.append({
            "ts": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else _now_iso(),
            "text": cmd,
            "agent": n.get("node_id", "?"),
            "ok": True,
            "latency_ms": n.get("last_latency_ms"),
        })
    out.sort(key=lambda c: c["ts"], reverse=True)
    return out[:RECENT_LIMIT]


def _latency(nodes: list[dict]) -> dict:
    lats = [n.get("last_latency_ms") for n in nodes if n.get("last_latency_ms")]
    avg = round(sum(lats) / len(lats)) if lats else None
    return {"stt_ms": None, "llm_ms": avg, "haos_ms": None, "by_command": []}


def _users() -> list[dict]:
    data = _get(f"{CORE_URL}/users")
    users = list(data.values()) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    intents = _get(f"{CORE_URL}/intents") or []
    pending: dict[str, int] = {}
    if isinstance(intents, list):
        for it in intents:
            uid = it.get("user_id")
            if uid and it.get("status", "open") not in ("done", "closed", "cancelled"):
                pending[uid] = pending.get(uid, 0) + 1
    out = []
    for u in users:
        if not isinstance(u, dict):
            continue
        uid = u.get("id", "?")
        # login_email: email dedicado o, en su defecto, gcal_email (FASE 33.19).
        login_email = u.get("email") or u.get("gcal_email")
        out.append({
            "id": uid,
            "name": u.get("name", uid),
            "role": u.get("role", "user"),
            "intents_pending": pending.get(uid, 0),
            "email": login_email,
        })
    return out


_FETCH_INTERVAL = int(os.environ.get("VERSIONS_FETCH_INTERVAL", "1800"))   # cada cuánto fetch (s)
_last_fetch = 0.0


def _maybe_fetch(repos, de) -> None:
    """git fetch de los repos para conocer la ÚLTIMA versión disponible (origin/main + tags), con
    throttle (no en cada snapshot). Egress-only: el Brain sólo hace una conexión saliente a GitHub."""
    global _last_fetch
    import time
    if time.time() - _last_fetch < _FETCH_INTERVAL:
        return
    _last_fetch = time.time()
    for repo in repos.values():
        de._run(["git", "-C", repo.git_dir(), "fetch", "--quiet", "--tags", "origin"],
                de._noop_emit, timeout=60)


def _repo_git_info(de, repo) -> dict:
    """sha+tag+link que CORRE y la ÚLTIMA disponible (origin/main + mayor tag semver) de un repo."""
    gd = repo.git_dir()
    sha = repo.head(de._noop_emit)
    tag = de._tag_at(gd, sha, de._noop_emit) if sha else None
    slug = de._repo_slug(gd, de._noop_emit)
    r = de._run(["git", "-C", gd, "rev-parse", "--short", "origin/main"], de._noop_emit, timeout=15)
    latest_sha = r.output.strip() if r.ok and r.output.strip() else None
    lv = de._latest_semver(gd, de._noop_emit)
    latest_tag = ("v%d.%d.%d" % lv) if lv else None

    def _gh(ref, is_tag):  # link a release si es tag, al commit si es sha — siempre hay link
        if not slug or not ref:
            return None
        return (f"https://github.com/{slug}/releases/tag/{ref}" if is_tag
                else f"https://github.com/{slug}/commit/{ref}")

    return {"sha": sha, "tag": tag, "url": _gh(tag or sha, bool(tag)),
            "latest_sha": latest_sha, "latest_tag": latest_tag,
            "latest_url": _gh(latest_tag or latest_sha, bool(latest_tag))}


def _versions(nodes: list[dict]) -> dict:
    """Matriz de TARGETS desplegables (34.15): UNA lista plana de cosas que corren — services del
    Brain (core/audio_server/backoffice), Cloud Run (cloud-bo) y un satélite por panel. Cada target
    lleva la versión que corre, la última disponible (origin/main + tag) con flag `behind`, links a
    GitHub, y el comando+params que lo despliega (el frontend sólo emite). Best-effort; nunca lanza."""
    out: dict = {"targets": [], "satellite_expected": None}
    ear_url = None
    try:
        import deploy_engine as de
        _maybe_fetch(de.REPOS, de)
        info = {name: _repo_git_info(de, repo) for name, repo in de.REPOS.items()}
        ear_url = info.get("ear", {}).get("url")
        cloud_state = de.load_state().get("cloud", {})
        for t in de.TARGETS:
            ri = info.get(t.repo, {})
            if t.kind == "cloudrun":
                cs = cloud_state.get(t.id, {})
                run_ver, run_url = cs.get("tag") or cs.get("version"), cs.get("url")
            else:
                run_ver, run_url = ri.get("tag") or ri.get("sha"), ri.get("url")
            latest_ver = ri.get("latest_tag") or ri.get("latest_sha")
            out["targets"].append({
                "id": t.id, "label": t.label, "where": t.where, "kind": t.kind,
                "advanced": t.advanced,
                "version": run_ver, "url": run_url,
                "latest": latest_ver, "latest_url": ri.get("latest_url"),
                # `behind` compara EXACTAMENTE lo que se muestra (tag vs tag, o sha vs sha si no hay
                # tag) — no el tag visible contra el sha de origin/main. Si no, un target tagueado a
                # la última release pero con main adelantado sin nuevo tag mostraba "misma versión +
                # rezagado".
                "behind": bool(run_ver and latest_ver and run_ver != latest_ver),
                "command": t.command, "params": t.params,
            })
    except Exception:
        pass
    expected = (_get(f"{AUDIO_URL}/satellite/version") or {}).get("version")
    out["satellite_expected"] = (expected or "")[:12] or None
    # Satélites: un target dinámico por panel. La versión es md5 de satellite.py/ui (no un sha git),
    # así que el link de referencia es el commit de ear que provee ese código. deploy.satellites
    # fuerza el pull del nodo.
    for n in nodes:
        v = n.get("version")
        out["targets"].append({
            "id": f"panel:{n.get('node_id')}", "label": n.get("node_id"),
            "where": "NSPanel", "kind": "satellite", "advanced": False,
            "version": (v or "")[:8] or None, "url": ear_url,
            "latest": (expected or "")[:8] or None, "latest_url": ear_url,
            "behind": bool(v and expected and expected[:12] != v),
            "command": "deploy.satellites", "params": {"node_id": n.get("node_id")},
        })
    return out


def _alerts() -> list[str]:
    """Alertas recientes SIN consumir la cola (FASE 37.7): usa /alerts/recent (peek), no
    /alerts (drain) — drenar le robaría alertas al satélite que las lee por TTS."""
    data = _get(f"{CORE_URL}/alerts/recent")
    return [str(a) for a in data][:RECENT_LIMIT] if isinstance(data, list) else []


def _counts() -> dict:
    """Conteos agregados (sin contenido PII en claro, FASE 37.1): sólo el largo de cada lista
    admin que el core ya expone. Nunca sale texto de intents/goals/rutinas/conversaciones."""
    def _len(path: str) -> int:
        d = _get(f"{CORE_URL}{path}")
        return len(d) if isinstance(d, list) else 0
    return {
        "intents":       _len("/intents"),
        "goals":         _len("/goals"),
        "routines":      _len("/routines"),
        "conversations": _len("/conversations"),
    }


def build_snapshot() -> dict:
    """Arma el snapshot completo. Nunca lanza: campos faltantes quedan vacíos."""
    nodes = _nodes()
    return {
        "schema_version": 1,
        "ts": _now_iso(),
        "host": HOST,
        "services": _services(),
        "latency": _latency(nodes),
        "agents": _agents(),
        "recent_commands": _recent_commands(nodes),
        "wakeword": _wakeword(nodes),
        "users_summary": _users(),
        "versions": _versions(nodes),
        "alerts": _alerts(),
        "counts": _counts(),
        "dashboards": _dashboards(),   # FASE 38: selector de dashboard del comando panel.config
        "models": _models(),           # FASE 43: selector de modelo del comando agent.config
    }

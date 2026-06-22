"""Executor seguro de comandos admin. FASE 33 (33.12).

Cada tipo del catálogo TIPADO mapea a una función concreta. NUNCA eval ni shell
arbitrario: subprocess siempre con lista de argumentos (sin shell=True) y los enums
ya vienen validados por el catálogo compartido (commands.py). Auditoría: el daemon
loguea cada comando, parámetros y resultado.
"""
from __future__ import annotations

import os
import subprocess

import requests

CORE_URL = os.environ.get("CORE_URL", "http://localhost:8765")
AUDIO_URL = os.environ.get("AUDIO_SERVER_URL", "http://localhost:8766")
REPO_DIR = os.environ.get("REPO_DIR", os.path.expanduser("~/workspace/home-agents"))
PIP = os.environ.get("PIP_BIN", os.path.expanduser("~/home-agents-env/bin/pip"))


class ExecResult:
    def __init__(self, ok: bool, output: str = "", error: str = ""):
        self.ok, self.output, self.error = ok, output, error

    def as_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output, "error": self.error}


def _run(args: list[str], timeout: int = 60) -> ExecResult:
    """Ejecuta un comando con lista de args (sin shell). Devuelve ExecResult."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return ExecResult(p.returncode == 0, out.strip(), "" if p.returncode == 0 else f"exit {p.returncode}")
    except subprocess.TimeoutExpired:
        return ExecResult(False, "", f"timeout tras {timeout}s")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", str(exc))


# ── Handlers por tipo ───────────────────────────────────────────────────────────

def _service_restart(p: dict) -> ExecResult:
    return _run(["systemctl", "--user", "restart", p["service"]], timeout=30)


def _service_status(p: dict) -> ExecResult:
    svc = p.get("service")
    units = [svc] if svc else ["capitan-core", "capitan-backoffice", "capitan-wa"]
    return _run(["systemctl", "--user", "is-active", *units], timeout=10)


def _logs_tail(p: dict) -> ExecResult:
    lines = str(p.get("lines", 100))
    return _run(["journalctl", "--user", "-u", p["service"], "-n", lines, "--no-pager"], timeout=15)


def _logs_satellite(p: dict) -> ExecResult:
    """FASE 37.10: log del satélite de un panel. No duplica el fetch: llama al audio_server
    (fuente única, que hace el ssh a Termux)."""
    lines = int(p.get("lines", 100))
    try:
        r = requests.get(f"{AUDIO_URL}/nodes/{p['node_id']}/satellite-log",
                         params={"lines": lines}, timeout=20)
        if r.status_code != 200:
            detail = (r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text)
            return ExecResult(False, "", f"audio_server {r.status_code}: {str(detail)[:200]}")
        return ExecResult(True, r.json().get("log", ""))
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"no se pudo traer el log del panel: {exc}")


def _run_engine(services, repo_refs, emit=None) -> ExecResult:
    """Invoca el MOTOR único de deploy (FASE 34). El executor NO reimplementa lógica de deploy:
    sólo traduce comando→args, corre el motor in-process (el bridge corre EN el Brain) y reporta
    el log incremental + el ok/rollback. `emit` (D5): callback de progreso en vivo — cada línea
    del motor se reenvía al cloud mientras el deploy corre. Ver deploy_engine.run_release / D1."""
    import deploy_engine
    lines: list[str] = []

    def _emit(line: str) -> None:
        lines.append(line)
        if emit:
            emit(line)

    res = deploy_engine.run_release(services, repo_refs or None, emit=_emit)
    err = "" if res.ok else "deploy con fallos (ver rollback en el log)"
    return ExecResult(res.ok, "\n".join(lines), err)


def _deploy_run(p: dict, emit=None) -> ExecResult:
    """Compat: deploy.run = release de los servicios default a HEAD de main (+ wa si restart_wa)."""
    import deploy_engine
    services = list(deploy_engine.DEFAULT_SERVICES) + (["wa"] if p.get("restart_wa") else [])
    return _run_engine(services, None, emit)


def _deploy_release(p: dict, emit=None) -> ExecResult:
    """FASE 34: release con pin de ref por repo. `services` acota qué desplegar (default del
    motor si se omite); core_ref/ear_ref/umbrella_ref pinean cada repo (default origin/main)."""
    repo_refs = {repo: p[key] for repo, key in
                 (("core", "core_ref"), ("ear", "ear_ref"), ("umbrella", "umbrella_ref"))
                 if p.get(key)}
    return _run_engine(p.get("services"), repo_refs, emit)


def _deploy_cloud(p: dict, emit=None) -> ExecResult:
    """FASE 34 T4: deploy de Cloud Run (cloud-bo) desde el Brain vía el motor (driver cloudrun)."""
    import deploy_engine
    targets = p.get("services") or list(deploy_engine.CLOUDRUN_TARGETS)
    lines: list[str] = []

    def _emit(line: str) -> None:
        lines.append(line)
        if emit:
            emit(line)

    res = deploy_engine.run_cloud_release(targets, emit=_emit)
    return ExecResult(res.ok, "\n".join(lines),
                      "" if res.ok else "deploy cloud con fallos (ver rollback en el log)")


def _deploy_satellites(p: dict) -> ExecResult:
    """34.16: fuerza el pull de código de uno o todos los paneles. Marca el nodo en el audio_server
    (POST /nodes/{id}/update); el satélite corre _check_code_update() en su próximo heartbeat. El
    pull en sí es egress-only (el panel baja del Brain). node_id ausente/'*' → todos los paneles."""
    node_id = p.get("node_id") or "*"
    try:
        r = requests.post(f"{AUDIO_URL}/nodes/{node_id}/update", timeout=10)
        r.raise_for_status()
        flagged = r.json().get("flagged", [])
        if not flagged:
            return ExecResult(True, "sin paneles para marcar (¿ninguno online?)")
        return ExecResult(True, f"marcados para actualizar: {', '.join(flagged)} "
                                f"(aplican en su próximo heartbeat, ~30s)")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"no se pudo marcar el panel: {exc}")


def _config_reload(p: dict) -> ExecResult:
    if p["target"] == "core":
        try:
            r = requests.post(f"{CORE_URL}/users/reload", timeout=10)
            r.raise_for_status()
            return ExecResult(True, f"core reload: {r.status_code}")
        except Exception as exc:  # noqa: BLE001
            return ExecResult(False, "", str(exc))
    return _run(["systemctl", "--user", "restart", "capitan-backoffice"], timeout=30)


def _wakeword_retrain(_p: dict) -> ExecResult:
    try:
        r = requests.post(f"{AUDIO_URL}/wakeword/train", timeout=15)
        r.raise_for_status()
        return ExecResult(True, f"retrain disparado: {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"endpoint de retrain no disponible: {exc}")


def _voice_reenroll(p: dict) -> ExecResult:
    try:
        r = requests.post(
            f"{AUDIO_URL}/nodes/{p['node_id']}/enroll/voice/{p['user_id']}", timeout=15
        )
        r.raise_for_status()
        return ExecResult(True, f"re-enroll disparado: {r.status_code}")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"endpoint de enroll no disponible: {exc}")


def _agent_toggle(p: dict) -> ExecResult:
    """FASE 37.8: cambia el status de un agente (PATCH /agents/{id}/status del core). El status
    ya viene validado por el catálogo (active/planned/unavailable)."""
    try:
        r = requests.patch(f"{CORE_URL}/agents/{p['agent_id']}/status",
                            json={"status": p["status"]}, timeout=10)
        r.raise_for_status()
        return ExecResult(True, f"{p['agent_id']} → {p['status']}")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"no se pudo cambiar el agente: {exc}")


def _proactive_run(p: dict) -> ExecResult:
    """FASE 37.8: dispara el ciclo proactivo de un agente (POST /proactive/{id}/run del core)."""
    try:
        r = requests.post(f"{CORE_URL}/proactive/{p['agent_id']}/run", timeout=60)
        r.raise_for_status()
        return ExecResult(True, f"proactivo {p['agent_id']}: {str(r.json())[:300]}")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"no se pudo correr el agente: {exc}")


NSPANEL_SCRIPT = os.environ.get("NSPANEL_SCRIPT", os.path.join(REPO_DIR, "scripts", "nspanel.sh"))


def _node_ip(node_id: str) -> str | None:
    try:
        nodes = requests.get(f"{AUDIO_URL}/nodes", timeout=8).json()
        for n in nodes if isinstance(nodes, list) else []:
            if n.get("node_id") == node_id:
                return n.get("ip")
    except Exception:  # noqa: BLE001
        return None
    return None


def _panel_reboot(p: dict) -> ExecResult:
    """FASE 37.8: reinicia un NSPanel reusando scripts/nspanel.sh (adb `su -c reboot`, el único
    camino de reboot del firmware eWeLink). Resuelve la IP del nodo desde el registro del
    audio_server y se la pasa al script por NSPANEL_IP. No reimplementa el reboot."""
    node_id = p["node_id"]
    ip = _node_ip(node_id)
    if not ip:
        return ExecResult(False, "", f"no encontré la IP del panel {node_id!r} (¿online?)")
    env = {**os.environ, "NSPANEL_IP": ip}
    try:
        proc = subprocess.run(["bash", NSPANEL_SCRIPT, "reboot"],
                              capture_output=True, text=True, timeout=30, env=env)
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        ok = proc.returncode == 0
        return ExecResult(ok, out, "" if ok else f"reboot falló (exit {proc.returncode})")
    except Exception as exc:  # noqa: BLE001
        return ExecResult(False, "", f"no se pudo reiniciar el panel: {exc}")


HANDLERS = {
    "service.restart": _service_restart,
    "service.status": _service_status,
    "logs.tail": _logs_tail,
    "logs.satellite": _logs_satellite,
    "deploy.run": _deploy_run,
    "deploy.release": _deploy_release,
    "deploy.cloud": _deploy_cloud,
    "deploy.satellites": _deploy_satellites,
    "config.reload": _config_reload,
    "wakeword.retrain": _wakeword_retrain,
    "voice.reenroll": _voice_reenroll,
    "agent.toggle": _agent_toggle,
    "panel.reboot": _panel_reboot,
    "proactive.run": _proactive_run,
}

# Comandos largos que emiten progreso EN VIVO (D5): el handler acepta un callback `emit` y va
# reportando líneas mientras corre (deploy). El resto es fire-and-result (sólo resultado final).
STREAMING = {"deploy.run", "deploy.release", "deploy.cloud"}


def execute(cmd_type: str, params: dict, emit=None) -> ExecResult:
    """Despacha al handler concreto. El tipo ya fue validado contra el catálogo. `emit`, si se
    pasa, recibe líneas de progreso en vivo para los comandos de STREAMING."""
    handler = HANDLERS.get(cmd_type)
    if handler is None:
        return ExecResult(False, "", f"sin handler para {cmd_type!r}")
    if cmd_type in STREAMING:
        return handler(params, emit)
    return handler(params)

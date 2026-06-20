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


def _run_engine(services, repo_refs) -> ExecResult:
    """Invoca el MOTOR único de deploy (FASE 34). El executor NO reimplementa lógica de deploy:
    sólo traduce comando→args, corre el motor in-process (el bridge corre EN el SER9) y reporta
    el log incremental + el ok/rollback. Ver deploy_engine.run_release / D1, D7."""
    import deploy_engine
    lines: list[str] = []
    res = deploy_engine.run_release(services, repo_refs or None, emit=lines.append)
    err = "" if res.ok else "deploy con fallos (ver rollback en el log)"
    return ExecResult(res.ok, "\n".join(lines), err)


def _deploy_run(p: dict) -> ExecResult:
    """Compat: deploy.run = release de los servicios default a HEAD de main (+ wa si restart_wa)."""
    import deploy_engine
    services = list(deploy_engine.DEFAULT_SERVICES) + (["wa"] if p.get("restart_wa") else [])
    return _run_engine(services, None)


def _deploy_release(p: dict) -> ExecResult:
    """FASE 34: release con pin de ref por repo. `services` acota qué desplegar (default del
    motor si se omite); core_ref/ear_ref/umbrella_ref pinean cada repo (default origin/main)."""
    repo_refs = {repo: p[key] for repo, key in
                 (("core", "core_ref"), ("ear", "ear_ref"), ("umbrella", "umbrella_ref"))
                 if p.get(key)}
    return _run_engine(p.get("services"), repo_refs)


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


HANDLERS = {
    "service.restart": _service_restart,
    "service.status": _service_status,
    "logs.tail": _logs_tail,
    "deploy.run": _deploy_run,
    "deploy.release": _deploy_release,
    "config.reload": _config_reload,
    "wakeword.retrain": _wakeword_retrain,
    "voice.reenroll": _voice_reenroll,
}


def execute(cmd_type: str, params: dict) -> ExecResult:
    """Despacha al handler concreto. El tipo ya fue validado contra el catálogo."""
    handler = HANDLERS.get(cmd_type)
    if handler is None:
        return ExecResult(False, "", f"sin handler para {cmd_type!r}")
    return handler(params)

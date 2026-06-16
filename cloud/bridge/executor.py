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


def _deploy_run(p: dict) -> ExecResult:
    out = []
    for step in (
        ["git", "-C", REPO_DIR, "pull", "--recurse-submodules"],
        [PIP, "install", "-q", "-r", os.path.join(REPO_DIR, "core/requirements.txt")],
        [PIP, "install", "-q", "-r", os.path.join(REPO_DIR, "backoffice/requirements.txt")],
        ["systemctl", "--user", "restart", "capitan-core", "capitan-backoffice"],
    ):
        r = _run(step, timeout=180)
        out.append(f"$ {' '.join(step)}\n{r.output}")
        if not r.ok:
            return ExecResult(False, "\n".join(out), r.error)
    if p.get("restart_wa"):
        r = _run(["systemctl", "--user", "restart", "capitan-wa"], timeout=30)
        out.append(f"restart wa: {r.output}")
    return ExecResult(True, "\n".join(out))


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

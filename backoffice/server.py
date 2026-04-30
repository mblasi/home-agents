#!/usr/bin/env python3
"""
Backoffice web para la red de agentes Capitán.

Panel de administración local-first en :8080.
Agrega datos del core (:8765), /tmp/capitan/ y journalctl.

Uso:
    source ~/home-agents-env/bin/activate
    cd ~/workspace/home-agents/backoffice
    uvicorn server:app --host 0.0.0.0 --port 8080

    # o via systemd:
    systemctl --user start capitan-backoffice
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import secrets

import requests
from fastapi import Cookie, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

# ── Configuración ──────────────────────────────────────────────────────────────

CORE_URL   = os.environ.get("CORE_URL",   "http://localhost:8765")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
BACKOFFICE_TOKEN = os.environ.get("BACKOFFICE_TOKEN", "")
METRICS_DIR   = Path("/tmp/capitan")
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="capitan-backoffice", version="1.0")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ── Auth ───────────────────────────────────────────────────────────────────────

_SESSION_COOKIE = "capitan_session"
_SESSIONS: set[str] = set()


def _new_session() -> str:
    tok = secrets.token_urlsafe(32)
    _SESSIONS.add(tok)
    return tok


def _check_auth(request: Request) -> bool:
    if not BACKOFFICE_TOKEN:
        return True  # sin token configurado, acceso libre (solo LAN)
    session = request.cookies.get(_SESSION_COOKIE, "")
    return session in _SESSIONS


def _require_auth(request: Request):
    if not _check_auth(request):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {"error": error})


@app.post("/login")
async def do_login(response: Response, token: str = Form(...)):
    if not BACKOFFICE_TOKEN or secrets.compare_digest(token, BACKOFFICE_TOKEN):
        session = _new_session()
        resp = RedirectResponse("/dashboard", status_code=303)
        resp.set_cookie(_SESSION_COOKIE, session, httponly=True, samesite="lax")
        return resp
    return RedirectResponse("/login?error=Token+incorrecto", status_code=303)


@app.get("/logout")
def logout(request: Request, response: Response):
    session = request.cookies.get(_SESSION_COOKIE, "")
    _SESSIONS.discard(session)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(_SESSION_COOKIE)
    return resp


# Middleware de autenticación — protege todas las rutas excepto /login
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        public = {"/login", "/api/status"}
        if request.url.path not in public and not request.url.path.startswith("/login"):
            if not _check_auth(request):
                return RedirectResponse("/login", status_code=303)
        return await call_next(request)

app.add_middleware(AuthMiddleware)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _core(path: str, method: str = "GET", **kwargs):
    """Llama al core con timeout corto; devuelve None si falla."""
    try:
        r = requests.request(method, f"{CORE_URL}{path}", timeout=3, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _read_json(filename: str):
    try:
        with open(METRICS_DIR / filename) as f:
            return json.load(f)
    except Exception:
        return None


def _render(request: Request, template: str, section: str, **ctx):
    return templates.TemplateResponse(
        request,
        template,
        {"section": section, "now": time.time(), **ctx},
    )


# ── Status parcial (HTMX polling) ─────────────────────────────────────────────

@app.get("/api/status", response_class=HTMLResponse)
def api_status():
    health = _core("/health") or {}
    ollama_ok = health.get("ollama", False)
    haos_ok   = health.get("haos",   False)
    core_ok   = health is not None

    def dot(ok: bool) -> str:
        return "🟢" if ok else "🔴"

    lines = [
        f'<div class="flex justify-between"><span class="text-gray-400">Core</span>'
        f'<span>{dot(core_ok)} {"OK" if core_ok else "down"}</span></div>',
        f'<div class="flex justify-between"><span class="text-gray-400">Ollama</span>'
        f'<span>{dot(ollama_ok)} {"OK" if ollama_ok else "down"}</span></div>',
        f'<div class="flex justify-between"><span class="text-gray-400">HAOS</span>'
        f'<span>{dot(haos_ok)} {"OK" if haos_ok else "down"}</span></div>',
    ]
    return HTMLResponse("\n".join(lines))


# ── Secciones ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/dashboard")


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    health  = _core("/health") or {}
    history = _read_json("history.json") or []
    alerts  = _core("/alerts") or []
    state   = _read_json("state.json") or {}

    # Latencias promedio de la sesión
    lats = {"stt": [], "llm": [], "total": []}
    for h in history:
        if h.get("lat_stt"):  lats["stt"].append(h["lat_stt"])
        if h.get("lat_llm"):  lats["llm"].append(h["lat_llm"])
        if h.get("lat_total"):lats["total"].append(h["lat_total"])

    avg = {k: round(sum(v)/len(v), 2) if v else None for k, v in lats.items()}

    return _render(request, "dashboard.html", "dashboard",
                   health=health, history=history[-10:],
                   alerts=alerts, state=state,
                   avg_lat=avg, history_count=len(history))


@app.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request):
    data = _core("/agents") or {}
    return _render(request, "agents.html", "agents", agents=data)


@app.post("/agents/{agent_id}/toggle", response_class=HTMLResponse)
async def toggle_agent(agent_id: str):
    # Stub: toggle requiere endpoint en core (tarea futura)
    return HTMLResponse(f'<span class="text-yellow-400 text-xs">toggle pendiente</span>')


@app.get("/shared-state", response_class=HTMLResponse)
def shared_state_page(request: Request):
    data = _core("/shared-state") or {}
    return _render(request, "shared_state.html", "shared-state", entries=data)


@app.delete("/shared-state/{key}", response_class=HTMLResponse)
def delete_state_key(key: str):
    _core(f"/shared-state/{key}", method="DELETE")
    return HTMLResponse("")


@app.get("/conversations", response_class=HTMLResponse)
def conversations_page(request: Request, status: str = "all"):
    data = _core("/conversations") or []
    if status != "all":
        data = [c for c in data if c.get("state") == status]
    return _render(request, "conversations.html", "conversations",
                   convs=data, status_filter=status)


@app.delete("/conversations/{conv_id}", response_class=HTMLResponse)
def close_conv(conv_id: str):
    _core(f"/conversations/{conv_id}", method="DELETE")
    return HTMLResponse("")


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request):
    history = _read_json("history.json") or []
    return _render(request, "stats.html", "stats", history=history)


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request):
    data = _core("/alerts") or []
    ss   = _core("/shared-state") or {}
    alert_keys = {k: v for k, v in ss.items() if "alert" in k.lower()}
    return _render(request, "alerts.html", "alerts",
                   alerts=data, alert_state=alert_keys)


@app.get("/config", response_class=HTMLResponse)
def config_page(request: Request):
    env_path = Path.home() / "workspace/home-agents/core/.env"
    env_vars: dict[str, str] = {}
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env_vars[k.strip()] = v.strip()
    except Exception:
        pass
    # Ocultar tokens
    safe = {k: ("***" if "TOKEN" in k or "KEY" in k or "SECRET" in k else v)
            for k, v in env_vars.items()}
    return _render(request, "config.html", "config", env_vars=safe)


@app.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request):
    devices = _read_json("devices.json") or {}
    return _render(request, "devices.html", "devices", devices=devices)


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    data = _core("/users") or {}
    return _render(request, "users.html", "users", users=data)


@app.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    return _render(request, "logs.html", "logs")


@app.get("/logs/stream")
def logs_stream(service: str = "all"):
    """SSE: journalctl en tiempo real."""
    units = []
    if service in ("all", "core"):    units += ["-u", "capitan-core"]
    if service in ("all", "ear"):     units += ["-u", "capitan"]
    if service in ("all", "backoffice"): units += ["-u", "capitan-backoffice"]
    if not units:
        units = ["-u", "capitan-core", "-u", "capitan", "-u", "capitan-backoffice"]

    def _gen():
        cmd = ["journalctl", "--user", "-f", "-n", "50", "--output=short"] + units
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True) as proc:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                level = "text-red-400" if "ERROR" in line or "error" in line else \
                        "text-yellow-400" if "WARN" in line or "Warning" in line else \
                        "text-gray-300"
                safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                yield f'data: <div class="{level} font-mono text-xs leading-5 whitespace-pre-wrap">{safe}</div>\n\n'
    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/integrations", response_class=HTMLResponse)
def integrations_page(request: Request):
    health = _core("/health") or {}
    agents = _core("/agents") or {}

    # Test Ollama models
    ollama_models = []
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            ollama_models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass

    return _render(request, "integrations.html", "integrations",
                   health=health, agents=agents, ollama_models=ollama_models)

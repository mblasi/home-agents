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
from fastapi import Cookie, FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

# ── Configuración ──────────────────────────────────────────────────────────────

CORE_URL      = os.environ.get("CORE_URL",      "http://localhost:8765")
AUDIO_SERVER_URL = os.environ.get("AUDIO_SERVER_URL", "http://localhost:8766")
_LLM_BASE_URL = (os.environ.get("LLM_BASE_URL") or os.environ.get("OLLAMA_URL") or "http://localhost:11434")
BACKOFFICE_TOKEN = os.environ.get("BACKOFFICE_TOKEN", "")
OAUTH_APP_URL = os.environ.get("OAUTH_APP_URL", "").rstrip("/")
METRICS_DIR   = Path("/tmp/capitan")
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="capitan-backoffice", version="1.0")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

import datetime as _dt
import json as _json_mod

def _datetimefmt(ts: float | int) -> str:
    try:
        return _dt.datetime.fromtimestamp(float(ts)).strftime("%d/%m %H:%M")
    except Exception:
        return "—"

def _tojson_filter(value, indent=None):
    """tojson que serializa objetos con ._d (wrapper de dicts del trace)."""
    def _default(o):
        if hasattr(o, "_d"):
            return o._d
        raise TypeError(type(o))
    return _json_mod.dumps(value, default=_default, ensure_ascii=False, indent=indent)

templates.env.filters["datetimefmt"] = _datetimefmt
templates.env.filters["tojson"]      = _tojson_filter

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

_CAPITAN_DIR = Path.home() / ".local/share/capitan"

_OAUTH_SERVICES = {
    "ml": {
        "me_url": "https://api.mercadolibre.com/users/me",
        "label": "MercadoLibre",
    },
}


def _oauth_token_path(service: str, user_id: str) -> Path:
    return _CAPITAN_DIR / f"{service}_token_{user_id}.json"


def _oauth_status(service: str, user_id: str) -> dict:
    path = _oauth_token_path(service, user_id)
    if not path.exists():
        return {"connected": False, "online": False}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {"connected": False, "online": False}

    token  = data.get("access_token", "")
    me_url = (_OAUTH_SERVICES.get(service) or {}).get("me_url", "")
    online = False
    if token and me_url:
        try:
            r = requests.get(me_url, headers={"Authorization": f"Bearer {token}"}, timeout=3)
            online = r.status_code == 200
        except Exception:
            pass

    return {
        "connected": True,
        "online":    online,
        "api_user_id": str(data.get("user_id", "")),
        "saved_at":    data.get("saved_at", ""),
    }


def _core(path: str, method: str = "GET", timeout: int = 3, **kwargs):
    """Llama al core con timeout corto; devuelve None si falla."""
    try:
        r = requests.request(method, f"{CORE_URL}{path}", timeout=timeout, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _audio(path: str, method: str = "GET", timeout: int = 5, **kwargs):
    """Llama al audio_server (node-facing: registry de nodos + canal de enrollment, 16.21)."""
    try:
        r = requests.request(method, f"{AUDIO_SERVER_URL}{path}", timeout=timeout, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _panels() -> list[dict]:
    """Registro de paneles (16.23). Lee panels.yaml de la raíz del repo."""
    try:
        import yaml
        p = Path(__file__).parent.parent / "panels.yaml"
        if not p.is_file():
            return []
        return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("panels", []) or []
    except Exception:
        return []


def _llm_ok() -> bool:
    try:
        return requests.get(f"{_LLM_BASE_URL}/api/tags", timeout=2).status_code == 200
    except Exception:
        return False


def _get_llm_models() -> list[str]:
    """Devuelve los nombres de modelos disponibles en el backend LLM."""
    try:
        r = requests.get(f"{_LLM_BASE_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


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
    core_ok   = _core("/health") is not None
    llm_ok = _llm_ok()
    ear_state = _ear_state()
    ear_ok    = ear_state is not None and ear_state.get("state") != "stopped"

    def dot(ok: bool) -> str:
        return "🟢" if ok else "🔴"

    lines = [
        f'<div class="flex justify-between"><span class="text-gray-400">Core</span>'
        f'<span>{dot(core_ok)} {"OK" if core_ok else "down"}</span></div>',
        f'<div class="flex justify-between"><span class="text-gray-400">LLM</span>'
        f'<span>{dot(llm_ok)} {"OK" if llm_ok else "down"}</span></div>',
        f'<div class="flex justify-between"><span class="text-gray-400">Ear</span>'
        f'<span>{dot(ear_ok)} {ear_state["state"] if ear_ok and ear_state else "off"}</span></div>',
    ]
    return HTMLResponse("\n".join(lines))


# ── Secciones ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/chat")


# ── Chat (17.2–17.4) ───────────────────────────────────────────────────────────

@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    _require_auth(request)
    users_resp = _core("/users") or {}
    users = list(users_resp.values()) if isinstance(users_resp, dict) else (users_resp if isinstance(users_resp, list) else [])
    return templates.TemplateResponse(request, "chat.html", {"users": users})


@app.post("/api/chat/send")
def chat_send(request: Request, text: str = Form(...), user_id: str = Form(""), conversation_id: str = Form("")):
    _require_auth(request)
    source: dict = {"channel": "chat"}
    if user_id:
        source["speaker_id"] = user_id

    body: dict = {"text": text, "source": source}
    if conversation_id:
        body["conversation_id"] = conversation_id

    def _relay():
        try:
            with requests.post(
                f"{CORE_URL}/process/stream",
                json=body,
                stream=True,
                timeout=60,
            ) as r:
                for raw in r.iter_lines():
                    if raw:
                        yield raw.decode() + "\n"
                    else:
                        yield "\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        _relay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/chat/conversations")
def api_chat_conversations(request: Request):
    _require_auth(request)
    data = _core("/conversations") or []
    data.sort(key=lambda c: c.get("updated_at", 0), reverse=True)
    return data


@app.get("/api/chat/conversations/{conv_id}")
def api_chat_conversation_detail(request: Request, conv_id: str):
    _require_auth(request)
    data = _core(f"/conversations/{conv_id}")
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    return data


@app.get("/api/chat/users/{user_id}/intents")
def api_chat_user_intents(request: Request, user_id: str):
    _require_auth(request)
    data = _core(f"/users/{user_id}/intents") or []
    return data


_EAR_STALE_SECS = 180  # heartbeat cada 60s → 3x es margin seguro


def _ear_state() -> dict | None:
    """Devuelve state.json solo si el heartbeat en devices.json es reciente."""
    devices = _read_json("devices.json") or {}
    cutoff = time.time() - _EAR_STALE_SECS
    if not any(d.get("ts", 0) > cutoff for d in devices.values()):
        return None
    return _read_json("state.json") or None


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    core_ok   = _core("/health") is not None
    llm_ok = _llm_ok()
    history   = _read_json("history.json") or []
    alerts    = _core("/alerts") or []
    state     = _ear_state()

    # Latencias promedio de la sesión
    lats = {"stt": [], "llm": [], "total": []}
    for h in history:
        if h.get("lat_stt"):  lats["stt"].append(h["lat_stt"])
        if h.get("lat_llm"):  lats["llm"].append(h["lat_llm"])
        if h.get("lat_total"):lats["total"].append(h["lat_total"])

    avg = {k: round(sum(v)/len(v), 2) if v else None for k, v in lats.items()}

    speaker = _read_json("speaker.json") or {}
    agents_data = _core("/agents", timeout=10) or {}
    active_agents = {k: v for k, v in agents_data.items() if v.get("status") == "active"}
    active_intents = _core("/intents") or []

    return _render(request, "dashboard.html", "dashboard",
                   core_ok=core_ok, llm_ok=llm_ok,
                   history=history[-10:],
                   alerts=alerts, state=state, speaker=speaker,
                   avg_lat=avg, history_count=len(history),
                   active_agents=active_agents,
                   active_intents=active_intents[:5])


@app.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request):
    # /agents-meta es instantáneo (sin checks de conectividad)
    # La columna "Accesible" se carga después via JS por /api/agents/{aid}/reachable
    core_ok = _core("/health", timeout=3) is not None
    data    = _core("/agents-meta", timeout=5) if core_ok else None
    return _render(request, "agents.html", "agents", agents=data or {}, core_ok=core_ok)


@app.get("/api/agents/{agent_id}/reachable", response_class=HTMLResponse)
def api_agent_reachable(agent_id: str):
    """Fragmento HTML de accesibilidad para el lazy-load de la columna en /agents."""
    result   = _core(f"/agents/{agent_id}/reachable", timeout=8)
    reachable = (result or {}).get("reachable") if result else False
    if reachable is None:
        return '<span class="text-gray-600 text-xs">—</span>'
    if reachable == "partial":
        return '<span title="Parcialmente accesible" class="text-amber-400">●</span>'
    if reachable:
        return '<span title="Accesible" class="text-emerald-400">●</span>'
    return '<span title="No accesible" class="text-red-400">●</span>'


@app.get("/agents/{agent_id}/detail", response_class=HTMLResponse)
def agent_detail_page(request: Request, agent_id: str):
    agent = _core(f"/agents/{agent_id}")
    if not agent:
        return RedirectResponse("/agents", status_code=302)

    history = _read_json("history.json") or []
    agent_history = [h for h in history if h.get("agent") == agent_id]

    lats = {"stt": [], "llm": [], "total": []}
    for h in agent_history:
        if h.get("lat_stt"):   lats["stt"].append(h["lat_stt"])
        if h.get("lat_llm"):   lats["llm"].append(h["lat_llm"])
        if h.get("lat_total"): lats["total"].append(h["lat_total"])

    def _pct(vals, p):
        if not vals:
            return None
        s = sorted(vals)
        idx = int(len(s) * p / 100)
        return round(s[min(idx, len(s) - 1)], 2)

    stats = {
        "count":   len(agent_history),
        "p50_stt": _pct(lats["stt"], 50),   "p95_stt": _pct(lats["stt"], 95),
        "p50_llm": _pct(lats["llm"], 50),   "p95_llm": _pct(lats["llm"], 95),
        "p50_total": _pct(lats["total"], 50), "p95_total": _pct(lats["total"], 95),
    }

    role_perms = _core("/rbac/roles") or {}
    roles_with_access = [r for r, agents in role_perms.items() if agent_id in agents]

    conversations = _core("/conversations") or []

    all_intents = _core("/intents") or []
    agent_intents = [i for i in all_intents if i.get("agent_id") == agent_id]

    proactive_status = _core("/proactive/status", timeout=3) or {}
    proactive_info   = proactive_status.get(agent_id)

    return _render(request, "agent_detail.html", "agents",
                   agent_id=agent_id, agent=agent,
                   recent_history=agent_history[-15:],
                   stats=stats,
                   roles_with_access=roles_with_access,
                   conversations=conversations,
                   agent_intents=agent_intents,
                   proactive_info=proactive_info)


@app.post("/agents/{agent_id}/toggle", response_class=HTMLResponse)
async def toggle_agent(agent_id: str):
    info = _core(f"/agents/{agent_id}") or {}
    current = info.get("status", "planned")
    new_status = "planned" if current == "active" else "active"
    _core(f"/agents/{agent_id}/status", method="PATCH", json={"status": new_status})

    if new_status == "active":
        css = "bg-emerald-900/50 text-emerald-400 hover:bg-emerald-900"
    else:
        css = "bg-gray-800 text-gray-500 hover:bg-gray-700"

    return HTMLResponse(
        f'<button hx-post="/agents/{agent_id}/toggle" '
        f'hx-target="#status-cell-{agent_id}" hx-swap="innerHTML" '
        f'title="Click para cambiar estado" '
        f'class="cursor-pointer px-2 py-1 rounded text-xs font-medium transition-colors {css}">'
        f'{new_status}</button>'
    )


@app.post("/agents/{agent_id}/proactive/toggle", response_class=HTMLResponse)
async def toggle_agent_proactive(agent_id: str):
    agent = _core(f"/agents/{agent_id}") or {}
    current = agent.get("proactive_enabled", True)
    new_val = not current
    _core(f"/agents/{agent_id}/proactive", method="PATCH", json={"enabled": new_val})
    return HTMLResponse(_proactive_toggle_html(agent_id, new_val))


def _proactive_toggle_html(agent_id: str, enabled: bool) -> str:
    if enabled:
        css  = "bg-violet-900/40 text-violet-300 border-violet-700 hover:bg-violet-800/60"
        label = "proactivo: on"
    else:
        css  = "bg-gray-800 text-gray-500 border-gray-700 hover:bg-gray-700"
        label = "proactivo: off"
    return (
        f'<button id="proactive-toggle-{agent_id}" '
        f'hx-post="/agents/{agent_id}/proactive/toggle" '
        f'hx-target="#proactive-toggle-{agent_id}" hx-swap="outerHTML" '
        f'class="px-3 py-1.5 border text-xs font-medium rounded-lg transition-colors {css}">'
        f'{label}</button>'
    )


@app.post("/agents/{agent_id}/proactive/run", response_class=HTMLResponse)
async def proactive_run(agent_id: str, request: Request):
    result = _core(f"/proactive/{agent_id}/run", method="POST", timeout=120)
    if not result:
        return HTMLResponse(
            '<span class="text-red-400">Error al ejecutar — el agente no está registrado o el core no responde.</span>'
        )
    users_checked   = result.get("users_checked", 0)
    intents_created = result.get("intents_created", 0)
    return HTMLResponse(
        f'<span class="text-violet-300">✓ Ejecutado — {users_checked} usuario(s) evaluado(s), '
        f'{intents_created} intento(s) creado(s).</span>'
    )


@app.get("/agents/{agent_id}/tools", response_class=HTMLResponse)
def agent_tools_partial(agent_id: str, request: Request):
    tools = _core(f"/agents/{agent_id}/tools") or []
    agent = _core(f"/agents/{agent_id}") or {}
    has_sources = bool((agent.get("tool_sources") or []))
    return templates.TemplateResponse(
        request, "agent_tools_partial.html",
        {"agent_id": agent_id, "tools": tools, "has_tool_sources": has_sources,
         "refresh_result": None},
    )


@app.post("/agents/{agent_id}/tools/refresh", response_class=HTMLResponse)
def agent_tools_refresh(agent_id: str, request: Request):
    result = _core(f"/agents/{agent_id}/tools/refresh", method="POST") or {}
    tools  = result.pop("tools", [])
    agent  = _core(f"/agents/{agent_id}") or {}
    has_sources = bool((agent.get("tool_sources") or []))
    return templates.TemplateResponse(
        request, "agent_tools_partial.html",
        {"agent_id": agent_id, "tools": tools, "has_tool_sources": has_sources,
         "refresh_result": result},
    )


@app.patch("/agents/{agent_id}/tools/{tool_name}", response_class=HTMLResponse)
async def agent_tool_toggle(agent_id: str, tool_name: str, request: Request):
    body = await request.json()
    _core(f"/agents/{agent_id}/tools/{tool_name}", method="PATCH", json=body)
    tools  = _core(f"/agents/{agent_id}/tools") or []
    agent  = _core(f"/agents/{agent_id}") or {}
    has_sources = bool((agent.get("tool_sources") or []))
    return templates.TemplateResponse(
        request, "agent_tools_partial.html",
        {"agent_id": agent_id, "tools": tools, "has_tool_sources": has_sources,
         "refresh_result": None},
    )


_ROLES_AGENTS = ["admin", "familiar", "adolescente", "niño", "invitado", "guest"]


@app.get("/agents/new", response_class=HTMLResponse)
def agent_new_page(request: Request):
    role_perms = _core("/rbac/roles") or {}
    return _render(request, "agent_new.html", "agents",
                   error="", role_perms=role_perms, roles=_ROLES_AGENTS,
                   llm_models=_get_llm_models())


@app.post("/agents/new")
async def agent_new_submit(request: Request):
    form = await request.form()
    default_roles = [r for r in _ROLES_AGENTS if r != "admin" and form.get(f"role_{r}")]
    payload = {
        "id":            str(form.get("id", "")).strip().lower().replace(" ", "_"),
        "name":          str(form.get("name", "")).strip(),
        "fancy_name":    str(form.get("fancy_name", "")).strip(),
        "icon":          str(form.get("icon", "")).strip(),
        "desc":          str(form.get("desc", "")).strip(),
        "status":        str(form.get("status", "planned")),
        "default_roles": default_roles,
        "system_prompt": str(form.get("system_prompt", "")).strip(),
        "backend":       str(form.get("backend", "ollama")),
        "model":         str(form.get("model", "qwen2.5:7b")),
    }
    result = _core("/agents", method="POST", json=payload)
    if result is None:
        role_perms = _core("/rbac/roles") or {}
        return _render(request, "agent_new.html", "agents",
                       error="No se pudo crear el agente (¿ID ya existe?)",
                       role_perms=role_perms, roles=_ROLES_AGENTS,
                       llm_models=_get_llm_models())
    examples_raw = str(form.get("examples", "")).strip()
    if examples_raw:
        examples = [l.strip() for l in examples_raw.splitlines() if l.strip()]
        if examples:
            _core(f"/agents/{payload['id']}/examples", method="PATCH", json={"examples": examples})
    return RedirectResponse(f"/agents/{payload['id']}", status_code=303)


@app.get("/agents/{agent_id}/edit", response_class=HTMLResponse)
def agent_edit_page(request: Request, agent_id: str, connected: str = "", oauth_error: str = "", saved: str = ""):
    agent = _core(f"/agents/{agent_id}")
    if not agent:
        return RedirectResponse("/agents", status_code=303)
    role_perms = _core("/rbac/roles") or {}
    users = _core("/users") or {}

    oauth_statuses: dict[str, dict[str, dict]] = {}
    for b in (agent.get("backends") or []):
        if b.get("type") == "oauth2":
            svc = b.get("service", "")
            oauth_statuses[svc] = {
                uid: _oauth_status(svc, uid) for uid in users
            }

    all_agents = _core("/agents", timeout=10) or {}
    return _render(request, "agent_edit.html", "agents",
                   agent=agent, agent_id=agent_id, error="",
                   role_perms=role_perms, roles=_ROLES_AGENTS,
                   llm_models=_get_llm_models(),
                   users=users, oauth_statuses=oauth_statuses,
                   just_connected=connected, oauth_error=oauth_error,
                   just_saved=saved, oauth_app_url=OAUTH_APP_URL,
                   all_agents=all_agents)


@app.post("/agents/{agent_id}/edit")
async def agent_edit_submit(request: Request, agent_id: str):
    form = await request.form()

    # Nombre, nombre de fantasía, icono y descripción (agent card)
    name       = str(form.get("name", "")).strip()
    fancy_name = str(form.get("fancy_name", "")).strip()
    icon       = str(form.get("icon", "")).strip()
    desc       = str(form.get("desc", "")).strip()
    if name or fancy_name or icon or desc:
        _core(f"/agents/{agent_id}/metadata", method="PATCH",
              json={"name": name or None, "fancy_name": fancy_name or None,
                    "icon": icon or None, "desc": desc or None})

    # Status
    status = str(form.get("status", "")).strip()
    if status:
        _core(f"/agents/{agent_id}/status", method="PATCH", json={"status": status})

    # Ejemplos de la agent card: uno por línea
    ex_raw = str(form.get("examples", ""))
    examples = [e.strip().strip('"\'') for e in ex_raw.splitlines() if e.strip()]
    _core(f"/agents/{agent_id}/examples", method="PATCH", json={"examples": examples})

    # Config: campos dinámicos según config_schema del agente
    agent_info = _core(f"/agents/{agent_id}") or {}
    schema = agent_info.get("config_schema") or {}
    config: dict = {}
    for key, meta in schema.items():
        raw_val = form.get(f"config_{key}")
        if raw_val is None:
            continue
        val_str = str(raw_val).strip()
        t = meta.get("type", "str")
        try:
            if t == "float":
                config[key] = float(val_str)
            elif t == "int":
                config[key] = int(val_str)
            else:
                config[key] = val_str
        except (ValueError, TypeError):
            config[key] = val_str
    if config:
        _core(f"/agents/{agent_id}/config", method="PATCH", json=config)

    # User context schema (9.21)
    schema_json = str(form.get("user_context_schema_json", "")).strip()
    if schema_json:
        try:
            schema = json.loads(schema_json)
            if isinstance(schema, list):
                _core(f"/agents/{agent_id}/user-context-schema", method="PATCH",
                      json={"schema": schema})
        except Exception:
            pass

    # Shared state prefix de este agente
    ssp = str(form.get("shared_state_prefix", "")).strip() or None
    _core(f"/agents/{agent_id}/shared-state-prefix", method="PATCH",
          json={"shared_state_prefix": ssp})

    # Afinidades: reconstruir la lista desde los checkboxes afinity_*
    all_agents_data = _core("/agents", timeout=10) or {}
    affinities = [
        aid for aid in all_agents_data
        if aid != agent_id and form.get(f"affinity_{aid}")
    ]
    _core(f"/agents/{agent_id}/affinities", method="PUT", json={"affinities": affinities})

    # RBAC: actualizar roles según checkboxes
    role_perms_current = _core("/rbac/roles") or {}
    for role in _ROLES_AGENTS:
        if role == "admin":
            continue
        current_agents = set(role_perms_current.get(role, []))
        if "*" in current_agents:
            continue
        checked = bool(form.get(f"role_{role}"))
        if checked and agent_id not in current_agents:
            _core(f"/rbac/roles/{role}", method="PATCH",
                  json={"agents": sorted(current_agents | {agent_id})})
        elif not checked and agent_id in current_agents:
            _core(f"/rbac/roles/{role}", method="PATCH",
                  json={"agents": sorted(current_agents - {agent_id})})

    return RedirectResponse(f"/agents/{agent_id}/edit?saved=1", status_code=303)


@app.delete("/agents/{agent_id}", response_class=HTMLResponse)
def delete_agent_htmx(agent_id: str):
    _core(f"/agents/{agent_id}", method="DELETE")
    return HTMLResponse("")


# ── OAuth2 backends ─────────────────────────────────────────────────────────────

@app.get("/auth/{service}/connect")
def oauth_connect(service: str, user_id: str, agent_id: str = "", redirect_to: str = ""):
    """Inicia el flujo OAuth2: pide a core la URL y redirige al usuario."""
    result = _core(f"/auth/{service}/url", params={
        "user_id": user_id, "agent_id": agent_id, "redirect_to": redirect_to,
    })
    if not result or not result.get("url"):
        raise HTTPException(status_code=503, detail=f"Core no pudo generar la URL de autorización para {service}")
    return RedirectResponse(result["url"], status_code=302)


@app.get("/auth/{service}/callback")
def oauth_callback(service: str, code: str = "", state: str = "", error: str = ""):
    """Recibe el callback de ML/MP con el code, lo envía a core para canjearlo."""
    if error or not code:
        return RedirectResponse("/agents", status_code=302)
    result      = _core(f"/auth/{service}/callback", method="POST", json={"code": code, "state": state})
    redirect_to = (result or {}).get("redirect_to", "")
    agent_id    = (result or {}).get("agent_id", "")
    if redirect_to:
        redirect = f"{redirect_to}?connected=1"
    elif agent_id:
        redirect = f"/agents/{agent_id}/edit?connected=1"
    else:
        redirect = "/agents"
    return RedirectResponse(redirect, status_code=302)


@app.post("/auth/{service}/disconnect", response_class=HTMLResponse)
async def oauth_disconnect(request: Request, service: str):
    if service not in _OAUTH_SERVICES:
        raise HTTPException(status_code=404)
    form        = await request.form()
    user_id     = str(form.get("user_id",     "")).strip()
    agent_id    = str(form.get("agent_id",    "")).strip()
    redirect_to = str(form.get("redirect_to", "")).strip()
    _oauth_token_path(service, user_id).unlink(missing_ok=True)
    dest = redirect_to or (f"/agents/{agent_id}/edit" if agent_id else "/agents")
    return RedirectResponse(dest, status_code=303)


@app.post("/auth/{service}/fetch-shortcode")
async def oauth_fetch_shortcode(request: Request, service: str):
    """Recupera el token del oauth app por short_code y lo persiste localmente."""
    form        = await request.form()
    user_id     = str(form.get("user_id",     "")).strip()
    agent_id    = str(form.get("agent_id",    "")).strip()
    redirect_to = str(form.get("redirect_to", "")).strip()

    def _err(msg: str):
        if redirect_to:
            return RedirectResponse(f"{redirect_to}?oauth_error={msg}", status_code=303)
        err_redirect = f"/agents/{agent_id}/edit?oauth_error={msg}" if agent_id else "/agents"
        return RedirectResponse(err_redirect, status_code=303)

    if service not in _OAUTH_SERVICES:
        return _err("Servicio+desconocido")
    if not OAUTH_APP_URL:
        return _err("OAUTH_APP_URL+no+configurado")
    short_code = str(form.get("short_code", "")).strip()
    if not short_code or not user_id:
        return _err("short_code+y+user_id+son+requeridos")
    try:
        r = requests.get(f"{OAUTH_APP_URL}/tokens/{short_code}", timeout=10)
        if r.status_code == 404:
            return _err("short_code+no+encontrado+o+expirado+(TTL+5+min)")
        r.raise_for_status()
        data = r.json()
    except RedirectResponse:
        raise
    except Exception as exc:
        return _err(f"Error+al+contactar+oauth+app:+{exc}")
    import datetime as _dt3
    token_data = {
        "access_token":  data.get("access_token", ""),
        "refresh_token": data.get("refresh_token", ""),
        "expires_in":    data.get("expires_in", 21600),
        "expires_at":    time.time() + data.get("expires_in", 21600),
        "user_id":       data.get("api_user_id", ""),
        "saved_at":      _dt3.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _CAPITAN_DIR.mkdir(parents=True, exist_ok=True)
    _oauth_token_path(service, user_id).write_text(json.dumps(token_data, indent=2))
    dest = redirect_to or (f"/agents/{agent_id}/edit?connected=1" if agent_id else "/agents")
    return RedirectResponse(dest if "?" in dest else f"{dest}?connected=1", status_code=303)


@app.post("/auth/{service}/set-token")
async def oauth_set_token(request: Request, service: str):
    """Configura tokens OAuth manualmente, como fallback al circuito WA."""
    form          = await request.form()
    user_id       = str(form.get("user_id",       "")).strip()
    agent_id      = str(form.get("agent_id",      "")).strip()
    redirect_to   = str(form.get("redirect_to",   "")).strip()
    access_token  = str(form.get("access_token",  "")).strip()
    refresh_token = str(form.get("refresh_token", "")).strip()

    def _err(msg: str):
        if redirect_to:
            return RedirectResponse(f"{redirect_to}?oauth_error={msg}", status_code=303)
        err_redirect = f"/agents/{agent_id}/edit?oauth_error={msg}" if agent_id else "/agents"
        return RedirectResponse(err_redirect, status_code=303)

    if service not in _OAUTH_SERVICES:
        return _err("Servicio+desconocido")
    if not user_id or not access_token:
        return _err("user_id+y+access_token+son+requeridos")
    import datetime as _dt2
    token_data = {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "expires_in":    21600,
        "expires_at":    time.time() + 21600,
        "saved_at":      _dt2.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _CAPITAN_DIR.mkdir(parents=True, exist_ok=True)
    _oauth_token_path(service, user_id).write_text(json.dumps(token_data, indent=2))
    dest = redirect_to or (f"/agents/{agent_id}/edit?connected=1" if agent_id else "/agents")
    return RedirectResponse(dest if "?" in dest else f"{dest}?connected=1", status_code=303)


@app.get("/intents", response_class=HTMLResponse)
def intents_page(request: Request):
    """Vista de primer nivel: todas las intenciones activas de todos los usuarios."""
    users_data  = _core("/users") or {}
    agents_data = _core("/agents", timeout=10) or {}
    all_intents = _core("/intents") or []
    return _render(request, "intents.html", "intents",
                   intents=all_intents, users=users_data, agents=agents_data)


@app.patch("/users/{uid}/intents/{intent_id}", response_class=HTMLResponse)
async def update_intent_proxy(uid: str, intent_id: str, request: Request):
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    _core(f"/users/{uid}/intents/{intent_id}", method="PATCH", json=body)
    return HTMLResponse("")


@app.delete("/users/{uid}/intents/{intent_id}", response_class=HTMLResponse)
def delete_intent_proxy(uid: str, intent_id: str):
    _core(f"/users/{uid}/intents/{intent_id}", method="DELETE")
    return HTMLResponse("")


@app.post("/users/{uid}/intents/{intent_id}/capture", response_class=HTMLResponse)
async def capture_intent_proxy(uid: str, intent_id: str, request: Request):
    """Captura manual de respuesta para un request intent (22.10)."""
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    reply = body.get("reply", "").strip()
    if reply:
        _core(f"/users/{uid}/intents/{intent_id}/capture", method="POST", json={"reply": reply})
    row_id = f"intent-row-{intent_id}"
    return HTMLResponse(
        f'<div id="{row_id}" class="px-4 py-3 text-xs text-orange-400 bg-orange-950/30 border border-orange-900/40 rounded-xl">'
        f'✓ Respuesta capturada'
        f'<script>setTimeout(()=>document.getElementById("{row_id}")?.remove(),2000)</script>'
        f'</div>'
    )


# ── Goals (22.10) ─────────────────────────────────────────────────────────────

@app.get("/goals", response_class=HTMLResponse)
def goals_page(request: Request):
    users_data  = _core("/users") or {}
    agents_data = _core("/agents", timeout=10) or {}
    all_goals   = _core("/goals") or []
    return _render(request, "goals.html", "goals",
                   goals=all_goals, users=users_data, agents=agents_data)


@app.post("/goals/{uid}/{goal_id}/transition", response_class=HTMLResponse)
async def transition_goal_proxy(uid: str, goal_id: str, request: Request):
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    _core(f"/users/{uid}/goals/{goal_id}/transition", method="POST", json=body)
    return HTMLResponse("")


@app.delete("/goals/{uid}/{goal_id}", response_class=HTMLResponse)
def delete_goal_proxy(uid: str, goal_id: str):
    _core(f"/users/{uid}/goals/{goal_id}", method="DELETE")
    return HTMLResponse("")


@app.post("/users/{uid}/intents/{intent_id}/respond", response_class=HTMLResponse)
async def respond_intent_proxy(uid: str, intent_id: str, request: Request):
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    value = body.get("value", "").strip()
    if value:
        all_intents = _core(f"/users/{uid}/intents") or []
        intent = next((i for i in all_intents if i.get("intent_id") == intent_id), {})
        ctx = intent.get("context", {})
        field = ctx.get("required_field")
        agent_id = intent.get("agent_id")
        if field and agent_id:
            _core(f"/users/{uid}/context/{agent_id}", method="PATCH", json={field: value})
        _core(f"/users/{uid}/intents/{intent_id}", method="PATCH", json={"status": "done"})
    row_id = f"intent-row-{intent_id}"
    return HTMLResponse(
        f'<div id="{row_id}" class="px-4 py-3 text-xs text-emerald-400 bg-emerald-950/30 border border-emerald-900/40 rounded-xl">'
        f'✓ Guardado'
        f'<script>setTimeout(()=>document.getElementById("{row_id}")?.remove(),2000)</script>'
        f'</div>'
    )


# ── Routines ──────────────────────────────────────────────────────────────────

@app.get("/routines", response_class=HTMLResponse)
def routines_page(request: Request):
    users_data  = _core("/users") or {}
    agents_data = _core("/agents", timeout=10) or {}
    all_routines = []
    for uid in users_data:
        user_routines = _core(f"/users/{uid}/routines") or []
        all_routines.extend(user_routines)
    all_routines.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
    return _render(request, "routines.html", "routines",
                   routines=all_routines, users=users_data, agents=agents_data)


@app.post("/routines/{uid}/{routine_id}/transition", response_class=HTMLResponse)
async def transition_routine_proxy(uid: str, routine_id: str, request: Request):
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)
    _core(f"/users/{uid}/routines/{routine_id}/transition", method="POST", json=body)
    return HTMLResponse("")


@app.delete("/routines/{uid}/{routine_id}", response_class=HTMLResponse)
def delete_routine_proxy(uid: str, routine_id: str):
    _core(f"/users/{uid}/routines/{routine_id}", method="DELETE")
    return HTMLResponse("")


@app.get("/shared-state", response_class=HTMLResponse)
def shared_state_page(request: Request):
    data = _core("/shared-state") or {}
    return _render(request, "shared_state.html", "shared-state", entries=data)


@app.delete("/shared-state/{key}", response_class=HTMLResponse)
def delete_state_key(key: str):
    _core(f"/shared-state/{key}", method="DELETE")
    return HTMLResponse("")


@app.get("/conversations", response_class=HTMLResponse)
def conversations_page(request: Request, status: str = "all", page: int = 1):
    data = _core("/conversations") or []
    if status != "all":
        data = [c for c in data if c.get("state") == status]
    data.sort(key=lambda c: c.get("created_at", 0), reverse=True)
    page_size  = 20
    total      = len(data)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page       = max(1, min(page, total_pages))
    offset     = (page - 1) * page_size
    return _render(request, "conversations.html", "conversations",
                   convs=data[offset:offset + page_size],
                   status_filter=status,
                   page=page, total_pages=total_pages, total=total)


@app.delete("/conversations/{conv_id}", response_class=HTMLResponse)
def close_conv(conv_id: str):
    _core(f"/conversations/{conv_id}", method="DELETE")
    return HTMLResponse("")


@app.get("/conversations/{conv_id}/traces", response_class=HTMLResponse)
def trace_list(request: Request, conv_id: str):
    traces = _core(f"/conversations/{conv_id}/traces") or []
    return _render(request, "trace_list.html", "conversations",
                   traces=traces, conv_id=conv_id)


@app.get("/conversations/{conv_id}/traces/{trace_id}", response_class=HTMLResponse)
def trace_detail(request: Request, conv_id: str, trace_id: str):
    t = _core(f"/conversations/{conv_id}/traces/{trace_id}")
    if not t:
        return HTMLResponse("<p>Trace no encontrado</p>", status_code=404)

    class _Obj:
        """Acceso por atributo a un dict JSON del trace."""
        def __init__(self, d: dict):
            self._d = d
            for k, v in d.items():
                if isinstance(v, dict):
                    setattr(self, k, _Obj(v))
                elif isinstance(v, list):
                    setattr(self, k, [_Obj(i) if isinstance(i, dict) else i for i in v])
                else:
                    setattr(self, k, v)
        # Dict protocol — necesario para tojson, .items(), for k,v in ...
        def get(self, k, default=None):
            return getattr(self, k, default)
        def items(self):
            return self._d.items()
        def keys(self):
            return self._d.keys()
        def values(self):
            return self._d.values()
        def __iter__(self):
            return iter(self._d)
        def __len__(self):
            return len(self._d)

    return _render(request, "trace_detail.html", "conversations",
                   t=_Obj(t))


# ── Traces combinados (proactive + goal review) ────────────────────────────────

_TRACES_PAGE_SIZE = 25


@app.get("/traces", response_class=HTMLResponse)
def traces_page(request: Request, tab: str = "proactive", page: int = 1):
    _require_auth(request)
    agents_data = _core("/agents", timeout=10) or {}
    tab = tab if tab in ("proactive", "goals") else "proactive"

    if tab == "goals":
        goal_ids   = _core("/goals/traces") or []
        all_goals  = _core("/goals") or []
        gmap       = {g.get("intent_id", "")[:8]: g for g in all_goals}
        all_traces = []
        for gid in goal_ids:
            for t in (_core(f"/goals/traces/{gid}") or []):
                t["_goal"] = gmap.get(gid, {})
                all_traces.append(t)
    else:
        agent_ids  = _core("/proactive/traces") or []
        all_traces = []
        for aid in agent_ids:
            for t in (_core(f"/proactive/traces/{aid}") or []):
                t["_agent"] = agents_data.get(aid, {})
                all_traces.append(t)

    all_traces.sort(key=lambda t: t.get("ts", 0), reverse=True)
    total       = len(all_traces)
    total_pages = max(1, (total + _TRACES_PAGE_SIZE - 1) // _TRACES_PAGE_SIZE)
    page        = max(1, min(page, total_pages))
    traces      = all_traces[(page - 1) * _TRACES_PAGE_SIZE : page * _TRACES_PAGE_SIZE]

    return _render(request, "traces.html", "traces",
                   tab=tab, page=page, total_pages=total_pages, total=total,
                   traces=traces, agents=agents_data)


# ── Proactive traces ───────────────────────────────────────────────────────────

@app.get("/proactive/traces", response_class=HTMLResponse)
def proactive_traces_page(request: Request):
    _require_auth(request)
    agent_ids   = _core("/proactive/traces") or []
    proactive_status = _core("/proactive/status", timeout=3) or {}
    agents_data = _core("/agents", timeout=10) or {}
    return _render(request, "proactive_traces.html", "traces",
                   agent_ids=agent_ids, proactive_status=proactive_status, agents=agents_data)


@app.get("/proactive/traces/{agent_id}", response_class=HTMLResponse)
def proactive_trace_list_page(request: Request, agent_id: str):
    _require_auth(request)
    traces = _core(f"/proactive/traces/{agent_id}") or []
    agents_data = _core("/agents", timeout=10) or {}
    agent = agents_data.get(agent_id, {})
    return _render(request, "proactive_trace_list.html", "traces",
                   traces=traces, agent_id=agent_id, agent=agent)


@app.get("/proactive/traces/{agent_id}/{trace_id}", response_class=HTMLResponse)
def proactive_trace_detail_page(request: Request, agent_id: str, trace_id: str):
    _require_auth(request)
    t = _core(f"/proactive/traces/{agent_id}/{trace_id}")
    if not t:
        return HTMLResponse("<p>Trace no encontrado</p>", status_code=404)

    class _Obj:
        def __init__(self, d):
            if not isinstance(d, dict):
                return
            self._d = d
            for k, v in d.items():
                if isinstance(v, dict):
                    setattr(self, k, _Obj(v))
                elif isinstance(v, list):
                    setattr(self, k, [_Obj(i) if isinstance(i, dict) else i for i in v])
                else:
                    setattr(self, k, v)
        def get(self, k, default=None): return getattr(self, k, default)
        def items(self): return self._d.items()
        def __iter__(self): return iter(self._d)
        def __len__(self): return len(self._d)

    return _render(request, "proactive_trace_detail.html", "traces",
                   t=_Obj(t))


# ── Goal review traces ─────────────────────────────────────────────────────────

@app.get("/goals/traces", response_class=HTMLResponse)
def goal_traces_page(request: Request):
    _require_auth(request)
    goal_ids  = _core("/goals/traces") or []
    all_goals = _core("/goals") or []
    goals_by_short = {g.get("intent_id", "")[:8]: g for g in all_goals}
    return _render(request, "goal_traces.html", "traces",
                   goal_ids=goal_ids, goals_by_short=goals_by_short)


@app.get("/goals/traces/{goal_id}", response_class=HTMLResponse)
def goal_trace_list_page(request: Request, goal_id: str):
    _require_auth(request)
    traces    = _core(f"/goals/traces/{goal_id}") or []
    all_goals = _core("/goals") or []
    goal = next((g for g in all_goals if g.get("intent_id", "")[:8] == goal_id[:8]), {})
    return _render(request, "goal_trace_list.html", "traces",
                   traces=traces, goal_id=goal_id, goal=goal)


@app.get("/goals/traces/{goal_id}/{trace_id}", response_class=HTMLResponse)
def goal_trace_detail_page(request: Request, goal_id: str, trace_id: str):
    _require_auth(request)
    t = _core(f"/goals/traces/{goal_id}/{trace_id}")
    if not t:
        return HTMLResponse("<p>Trace no encontrado</p>", status_code=404)

    class _Obj:
        def __init__(self, d):
            if not isinstance(d, dict):
                return
            self._d = d
            for k, v in d.items():
                if isinstance(v, dict):
                    setattr(self, k, _Obj(v))
                elif isinstance(v, list):
                    setattr(self, k, [_Obj(i) if isinstance(i, dict) else i for i in v])
                else:
                    setattr(self, k, v)
        def get(self, k, default=None): return getattr(self, k, default)
        def items(self): return self._d.items()
        def __iter__(self): return iter(self._d)
        def __len__(self): return len(self._d)

    return _render(request, "goal_trace_detail.html", "traces",
                   t=_Obj(t))


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


@app.get("/users/{uid}/finance/templates", response_class=HTMLResponse)
def get_user_finance_templates_fragment(uid: str):
    templates = _core(f"/finance/plans/{uid}/templates") or []
    return HTMLResponse(_render_templates_rows(uid, templates))


@app.post("/users/{uid}/finance/templates", response_class=HTMLResponse)
async def create_user_finance_template(request: Request, uid: str):
    form      = await request.form()
    name      = str(form.get("name", "")).strip()
    raw_pos   = str(form.get("positions_raw", "")).strip()
    try:
        threshold = float(form.get("review_threshold") or -10)
    except ValueError:
        threshold = -10.0

    positions: list[dict] = []
    for part in raw_pos.split(","):
        part = part.strip()
        if ":" in part:
            ticker, pct_s = part.split(":", 1)
            try:
                positions.append({"ticker": ticker.strip().upper(), "pct": float(pct_s.strip())})
            except ValueError:
                pass

    if not name or not positions:
        return HTMLResponse('<p class="text-red-400 text-xs mt-1">Nombre y posiciones requeridos.</p>')

    _core(f"/finance/plans/{uid}/templates", method="POST",
          json={"name": name, "positions": positions, "review_threshold": threshold})

    templates = _core(f"/finance/plans/{uid}/templates") or []
    return HTMLResponse(_render_templates_rows(uid, templates))


@app.delete("/users/{uid}/finance/templates/{name}", response_class=HTMLResponse)
def delete_user_finance_template(uid: str, name: str):
    _core(f"/finance/plans/{uid}/templates/{name}", method="DELETE")
    return HTMLResponse("")


def _render_templates_rows(uid: str, templates: list[dict]) -> str:
    if not templates:
        return '<p class="text-xs text-gray-600 italic">Sin templates definidos.</p>'
    rows = []
    for t in templates:
        positions_str = ", ".join(
            f'{p["ticker"]} {p["pct"]:.0f}%' for p in t.get("positions", [])
        )
        threshold = t.get("review_threshold", -10.0)
        name_safe = t["name"].replace('"', "&quot;")
        rows.append(
            f'<div class="flex items-center gap-2 py-1.5 border-b border-gray-800 last:border-0">'
            f'  <span class="text-sm font-medium text-gray-200 w-28 shrink-0">{t["name"]}</span>'
            f'  <span class="text-xs text-gray-500 flex-1 font-mono">{positions_str}</span>'
            f'  <span class="text-xs font-mono shrink-0 '
            f'{"text-amber-400" if threshold >= -5 else "text-yellow-400" if threshold >= -10 else "text-red-400"}">'
            f'  {threshold:+.0f}%</span>'
            f'  <button hx-delete="/users/{uid}/finance/templates/{name_safe}"'
            f'    hx-target="closest div" hx-swap="outerHTML"'
            f'    hx-confirm="¿Eliminar template \'{name_safe}\'?"'
            f'    class="shrink-0 px-1.5 py-0.5 text-[10px] text-gray-600 hover:text-red-400'
            f'           hover:bg-red-900/20 rounded transition-colors">✕</button>'
            f'</div>'
        )
    return "".join(rows)


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


def _load_rbac_context() -> tuple[dict, dict]:
    """Devuelve (agents, role_perms) del core. Ambos son dicts."""
    agents = _core("/agents") or {}
    role_perms = _core("/rbac/roles") or {}
    return agents, role_perms


def _compute_agent_overrides(
    form, role: str, role_perms: dict, all_agent_ids: list[str]
) -> tuple[list[str], list[str]]:
    """Calcula grants y revocaciones a partir de los checkboxes del form.

    Devuelve (agent_ids, revoked_agents):
      agent_ids      — agentes marcados que el rol NO otorga (grants explícitos)
      revoked_agents — agentes NO marcados que el rol SÍ otorga (revocaciones explícitas)
    """
    role_grants = set(role_perms.get(role, []))
    if "*" in role_grants:
        role_grants = set(all_agent_ids)

    checked = {aid for aid in all_agent_ids if form.get(f"agent_{aid}")}

    agent_ids      = sorted(checked - role_grants)
    revoked_agents = sorted(role_grants - checked)
    return agent_ids, revoked_agents


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    data = _core("/users") or {}
    agents, role_perms = _load_rbac_context()
    return _render(request, "users.html", "users", users=data, agents=agents, role_perms=role_perms)


@app.get("/users/new", response_class=HTMLResponse)
def new_user_page(request: Request):
    agents, role_perms = _load_rbac_context()
    return _render(request, "user_form.html", "users",
                   user=None, uid=None, error="", agents=agents, role_perms=role_perms)


@app.post("/users/create")
async def create_user_submit(request: Request):
    form = await request.form()
    agents, role_perms = _load_rbac_context()
    role = str(form.get("role", "invitado"))
    agent_ids, revoked_agents = _compute_agent_overrides(
        form, role, role_perms, list(agents.keys())
    )
    payload = {
        "id":             str(form.get("id", "")).strip(),
        "name":           str(form.get("name", "")).strip(),
        "role":           role,
        "relationship":   str(form.get("relationship", "invitado")),
        "wa_phone":       str(form.get("wa_phone", "")).strip() or None,
        "agent_ids":      agent_ids,
        "revoked_agents": revoked_agents,
    }
    result = _core("/users", method="POST", json=payload)
    if result is None:
        return _render(request, "user_form.html", "users",
                       user=payload, uid=None, error="No se pudo crear el usuario (¿ID ya existe?)",
                       agents=agents, role_perms=role_perms)
    uid = payload["id"]
    return RedirectResponse(f"/users/{uid}", status_code=303)


@app.get("/users/{uid}", response_class=HTMLResponse)
def user_detail_page(request: Request, uid: str):
    user = _core(f"/users/{uid}")
    if not user:
        return RedirectResponse("/users", status_code=303)
    agents, _ = _load_rbac_context()
    # /agents-meta es instantáneo (sin connectivity checks) — usado para user_context_schema
    agents_meta  = _core("/agents-meta", timeout=5) or {}
    ww_samples   = _core(f"/users/{uid}/wakeword/samples") or {"count": 0, "required": 30, "samples": []}
    ww_metrics   = _core(f"/users/{uid}/wakeword/metrics") or {"tp": 0, "fp": 0, "rbac_deny": 0}
    train_status = _core("/wakeword/train/status") or {"status": "idle"}
    user_context     = _core(f"/users/{uid}/context/raw") or {}
    user_intents     = _core(f"/users/{uid}/intents", params={"active_only": True}) or []
    proactive_status = _core("/proactive/status", timeout=3) or {}
    # Solo agentes con proactividad habilitada globalmente
    proactive_status = {
        aid: info for aid, info in proactive_status.items()
        if agents.get(aid, {}).get("proactive_enabled", True)
    }
    # proactive_enabled per agent from plain context (not raw)
    user_ctx_plain   = _core(f"/users/{uid}/context") or {}
    ml_oauth_status  = _oauth_status("ml", uid)
    finance_plans    = _core(f"/finance/plans/{uid}") or []
    return _render(request, "user_detail.html", "users",
                   user=user, uid=uid, agents=agents, agents_meta=agents_meta,
                   ww_samples=ww_samples, ww_metrics=ww_metrics,
                   train_status=train_status, panels=_panels(),
                   user_context=user_context, user_intents=user_intents,
                   proactive_status=proactive_status,
                   user_ctx_plain=user_ctx_plain,
                   ml_oauth_status=ml_oauth_status,
                   finance_plans=finance_plans,
                   oauth_app_url=OAUTH_APP_URL,
                   connected=request.query_params.get("connected", ""),
                   oauth_error=request.query_params.get("oauth_error", ""))


@app.get("/users/{uid}/edit", response_class=HTMLResponse)
def edit_user_page(request: Request, uid: str):
    user = _core(f"/users/{uid}")
    if not user:
        return RedirectResponse("/users", status_code=303)
    agents, role_perms = _load_rbac_context()
    ww_samples   = _core(f"/users/{uid}/wakeword/samples") or {"count": 0, "required": 30, "samples": []}
    ww_metrics   = _core(f"/users/{uid}/wakeword/metrics") or {"tp": 0, "fp": 0, "rbac_deny": 0}
    train_status = _core("/wakeword/train/status") or {"status": "idle"}
    user_context = _core(f"/users/{uid}/context/raw") or {}
    user_intents = _core(f"/users/{uid}/intents", params={"active_only": True}) or []
    return _render(request, "user_form.html", "users",
                   user=user, uid=uid, error="", agents=agents, role_perms=role_perms,
                   ww_samples=ww_samples, ww_metrics=ww_metrics, train_status=train_status,
                   user_context=user_context, user_intents=user_intents)


@app.post("/users/{uid}/update")
async def update_user_submit(request: Request, uid: str):
    form = await request.form()
    agents, role_perms = _load_rbac_context()
    role = str(form.get("role", "invitado"))
    agent_ids, revoked_agents = _compute_agent_overrides(
        form, role, role_perms, list(agents.keys())
    )
    payload = {
        "name":           str(form.get("name", "")).strip(),
        "role":           role,
        "relationship":   str(form.get("relationship", "invitado")),
        "wa_phone":       str(form.get("wa_phone", "")).strip() or None,
        "agent_ids":      agent_ids,
        "revoked_agents": revoked_agents,
    }
    result = _core(f"/users/{uid}", method="PATCH", json=payload)
    if result is None:
        ww_samples   = _core(f"/users/{uid}/wakeword/samples") or {"count": 0, "required": 30, "samples": []}
        ww_metrics   = _core(f"/users/{uid}/wakeword/metrics") or {"tp": 0, "fp": 0, "rbac_deny": 0}
        train_status = _core("/wakeword/train/status") or {"status": "idle"}
        return _render(request, "user_form.html", "users",
                       user={**payload, "id": uid}, uid=uid,
                       error="No se pudo actualizar el usuario",
                       agents=agents, role_perms=role_perms,
                       ww_samples=ww_samples, ww_metrics=ww_metrics, train_status=train_status)
    return RedirectResponse("/users", status_code=303)


@app.delete("/users/{uid}", response_class=HTMLResponse)
def delete_user_htmx(uid: str):
    _core(f"/users/{uid}", method="DELETE")
    return HTMLResponse("")


@app.delete("/users/{uid}/context/{agent_id}/{field}", response_class=HTMLResponse)
def delete_user_context_field_proxy(uid: str, agent_id: str, field: str):
    _core(f"/users/{uid}/context/{agent_id}/{field}", method="DELETE")
    return HTMLResponse("")


@app.post("/users/{uid}/context/{agent_id}/{field}", response_class=HTMLResponse)
async def set_user_context_field(uid: str, agent_id: str, field: str, request: Request):
    form  = await request.form()
    value = str(form.get("value", "")).strip()
    if value:
        _core(f"/users/{uid}/context/{agent_id}", method="PATCH", json={field: value})
    return HTMLResponse(
        f'<span id="ctx-saved-{agent_id}-{field}" class="text-xs text-emerald-400">'
        f'✓ Guardado'
        f'<script>setTimeout(()=>document.getElementById("ctx-saved-{agent_id}-{field}")?.remove(),2000)</script>'
        f'</span>'
    )


@app.get("/users/{uid}/finance/plans/history")
def get_user_plans_history(request: Request, uid: str):
    plan_names = request.query_params.getlist("plan")
    interval   = request.query_params.get("interval", "1h")
    start      = request.query_params.get("start")
    end        = request.query_params.get("end")
    params: list = [("plan", n) for n in plan_names]
    params.append(("interval", interval))
    if start: params.append(("start", start))
    if end:   params.append(("end", end))
    data = _core(f"/finance/plans/{uid}/history", timeout=30, params=params) or {}
    return JSONResponse(data)


@app.get("/users/{uid}/finance/plans/evolution", response_class=HTMLResponse)
def user_plans_evolution(request: Request, uid: str):
    finance_plans = _core(f"/finance/plans/{uid}") or []
    return _render(request, "finance_pnl_history.html", "users",
                   uid=uid, finance_plans=finance_plans)


_POPULAR_TICKERS = [
    # ── CEDEARs / acciones globales ───────────────────────────────────────────
    {"symbol": "GGAL",   "name": "Galicia",             "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "MELI",   "name": "MercadoLibre",        "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "BABA",   "name": "Alibaba",             "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "AMZN",   "name": "Amazon",              "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "AAPL",   "name": "Apple",               "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "MSFT",   "name": "Microsoft",           "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "GOOGL",  "name": "Alphabet",            "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "META",   "name": "Meta",                "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "NVDA",   "name": "NVIDIA",              "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "TSLA",   "name": "Tesla",               "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "GOLD",   "name": "Barrick Gold",        "type": "Stock", "cat": "CEDEARs"},
    {"symbol": "GLOB",   "name": "Globant",             "type": "Stock", "cat": "CEDEARs"},
    # ── ETFs ─────────────────────────────────────────────────────────────────
    {"symbol": "SPY",    "name": "S&P 500 ETF",         "type": "ETF",   "cat": "ETFs"},
    {"symbol": "QQQ",    "name": "Nasdaq 100 ETF",      "type": "ETF",   "cat": "ETFs"},
    {"symbol": "VTI",    "name": "Total Market ETF",    "type": "ETF",   "cat": "ETFs"},
    # ── Cripto ───────────────────────────────────────────────────────────────
    {"symbol": "BTC-USD","name": "Bitcoin",             "type": "Crypto","cat": "Cripto"},
    {"symbol": "ETH-USD","name": "Ethereum",            "type": "Crypto","cat": "Cripto"},
    {"symbol": "SOL-USD","name": "Solana",              "type": "Crypto","cat": "Cripto"},
    # ── Commodities ──────────────────────────────────────────────────────────
    {"symbol": "GC=F",   "name": "Oro (Gold Futures)", "type": "Future","cat": "Commodities"},
    {"symbol": "CL=F",   "name": "Petróleo WTI",       "type": "Future","cat": "Commodities"},
    {"symbol": "SI=F",   "name": "Plata (Silver Fut)", "type": "Future","cat": "Commodities"},
    # ── Pares de moneda ───────────────────────────────────────────────────────
    {"symbol": "UYU=X",  "name": "USD/Peso Uruguayo",  "type": "FX",    "cat": "FX"},
]

_ticker_search_cache: dict[str, dict] = {}
_TICKER_SEARCH_TTL = 300  # 5 min

@app.get("/finance/tickers/popular")
def get_popular_tickers():
    return JSONResponse(_POPULAR_TICKERS)


@app.get("/finance/tickers/search")
def search_tickers(q: str = Query(default="")):
    q = q.strip()
    if not q:
        return JSONResponse([])
    key = q.upper()
    cached = _ticker_search_cache.get(key)
    if cached and (time.time() - cached["ts"]) < _TICKER_SEARCH_TTL:
        return JSONResponse(cached["data"])
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": q, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": "false"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        quotes = r.json().get("quotes", [])
        result = [
            {
                "symbol":   qt.get("symbol", ""),
                "name":     qt.get("shortname") or qt.get("longname") or "",
                "type":     qt.get("typeDisp", ""),
                "exchange": qt.get("exchDisp", ""),
            }
            for qt in quotes
            if qt.get("symbol")
        ]
        _ticker_search_cache[key] = {"data": result, "ts": time.time()}
        return JSONResponse(result)
    except Exception:
        return JSONResponse([])


@app.delete("/users/{uid}/finance/plans/{plan_name}", response_class=HTMLResponse)
def delete_user_finance_plan(uid: str, plan_name: str):
    _core(f"/finance/plans/{uid}/{plan_name}", method="DELETE")
    return HTMLResponse("")


@app.post("/users/{uid}/gcal", response_class=HTMLResponse)
async def save_gcal_credentials(request: Request, uid: str):
    form     = await request.form()
    email    = str(form.get("gcal_email",        "")).strip()
    password = str(form.get("gcal_app_password", "")).strip()
    # Remover espacios del app password (Google los muestra en grupos de 4)
    password = password.replace(" ", "")
    payload: dict = {"gcal_email": email or None}
    if password:
        payload["gcal_app_password"] = password
    result = _core(f"/users/{uid}", method="PATCH", json=payload)
    if result is None:
        return HTMLResponse('<span class="text-red-400">Error al guardar</span>')
    return HTMLResponse('<span class="text-emerald-400">Guardado</span>')


@app.delete("/users/{uid}/gcal", response_class=HTMLResponse)
def delete_gcal_credentials(uid: str):
    _core(f"/users/{uid}/gcal", method="DELETE")
    return HTMLResponse('<span class="text-gray-400">Eliminado — recargá la página</span>')


@app.post("/users/{uid}/preferences/{key}/toggle", response_class=HTMLResponse)
def toggle_user_preference(uid: str, key: str):
    user = _core(f"/users/{uid}") or {}
    prefs = dict(user.get("preferences") or {})
    if key == "wa_notify_format":
        current = prefs.get("wa_notify_format", "text")
        new_val = "audio" if current == "text" else "text"
        prefs["wa_notify_format"] = new_val
        _core(f"/users/{uid}", method="PATCH", json={"preferences": prefs})
        is_audio = new_val == "audio"
        cls  = "bg-blue-900/30 text-blue-300 border-blue-700" if is_audio else "bg-gray-800 text-gray-400 border-gray-700"
        label = "🔊 Audio" if is_audio else "💬 Texto"
        return HTMLResponse(
            f'<button id="wa-fmt-btn" '
            f'hx-post="/users/{uid}/preferences/wa_notify_format/toggle" '
            f'hx-target="#wa-fmt-btn" hx-swap="outerHTML" '
            f'class="text-xs px-2 py-0.5 rounded border transition-colors {cls}">'
            f'{label}</button>'
        )
    return HTMLResponse("", status_code=400)


@app.post("/users/{uid}/proactive/{agent_id}/toggle", response_class=HTMLResponse)
def toggle_proactive_for_user(uid: str, agent_id: str):
    ctx       = _core(f"/users/{uid}/context/{agent_id}") or {}
    raw_field = ctx.get("proactive_enabled")
    current   = raw_field.get("value", True) if isinstance(raw_field, dict) else (True if raw_field is None else raw_field)
    new_val   = not current
    _core(f"/users/{uid}/context/{agent_id}", method="PATCH", json={"proactive_enabled": new_val})
    on_cls  = "bg-violet-600 hover:bg-violet-500 text-white"
    off_cls = "bg-gray-700 hover:bg-gray-600 text-gray-400"
    label   = "🔄 Activo" if new_val else "⏸ Pausado"
    css     = on_cls if new_val else off_cls
    return HTMLResponse(
        f'<button hx-post="/users/{uid}/proactive/{agent_id}/toggle" '
        f'hx-target="this" hx-swap="outerHTML" '
        f'class="px-2 py-1 text-xs font-medium rounded-lg transition-colors {css}">'
        f'{label}</button>'
    )


@app.get("/users/{uid}/proactive/run-all")
def proactive_run_all_for_user(uid: str, concurrency: int = 3):
    """SSE proxy: retransmite el stream de core /proactive/run-for-user/{uid}."""
    def _relay():
        try:
            with requests.get(
                f"{CORE_URL}/proactive/run-for-user/{uid}",
                params={"concurrency": concurrency},
                stream=True,
                timeout=300,
            ) as r:
                for raw in r.iter_lines():
                    if raw:
                        yield raw.decode() + "\n"
                    else:
                        yield "\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        _relay(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Onboarding wizard ─────────────────────────────────────────────────────────

# ── Wake word global + enrollment por nodo (12.16 / 16.22 / 16.25) ────────────

def _enroll_session_fragment(node_id: str, target: str = "") -> str:
    """Fragmento HTMX con el estado de la sesión de enrollment en un nodo (16.21).
    `target` = id del contenedor que se auto-refresca (reusable: página global y de user)."""
    target = target or f"enroll-{node_id}"
    st = _audio(f"/nodes/{node_id}/enroll/status") or {"phase": "idle"}
    phase = st.get("phase", "idle")
    i, n = st.get("i", 0), st.get("n", 0)
    kind = st.get("type", "")
    label = "voz" if kind == "voice" else "wake word"
    poll = (f'<span hx-get="/nodes/{node_id}/enroll/status-fragment?target={target}"'
            f' hx-trigger="every 2s" hx-target="#{target}" hx-swap="innerHTML"></span>')
    if phase in ("pending", "recording", "uploading"):
        pct = int(i / n * 100) if n else 0
        verb = {"pending": "esperando al panel…", "recording": f"grabando {label} {i}/{n}",
                "uploading": f"subiendo {i}/{n}"}.get(phase, phase)
        return (f'<p class="text-sm text-blue-300 animate-pulse mb-1">{verb} — pedile a la persona '
                f'que hable tras cada beep en el panel</p>'
                f'<div class="w-full bg-gray-700 rounded-full h-2"><div class="bg-blue-500 h-2 '
                f'rounded-full transition-all" style="width:{pct}%"></div></div>{poll}')
    if phase == "done" and kind == "verify":
        conf = st.get("confidence", 0.0)
        if st.get("matches"):
            return (f'<p class="text-sm text-emerald-400">✓ voz reconocida — {st.get("speaker","?")} '
                    f'(confianza {conf}). El usuario queda operativo por voz.</p>')
        return (f'<p class="text-sm text-amber-300">⚠ no reconocida con suficiente confianza '
                f'(dio {st.get("speaker","?")} / {conf}). Reforzá el enrollment con más frases.</p>')
    if phase == "done":
        return f'<p class="text-sm text-emerald-400">✓ enrollment de {label} completo ({i}/{n})</p>'
    if phase == "error":
        return '<p class="text-sm text-red-400">✗ error en el enrollment</p>'
    return '<p class="text-xs text-gray-500">sin sesión activa</p>'


@app.post("/nodes/{node_id}/enroll/{kind}/{uid}", response_class=HTMLResponse)
def trigger_node_enroll(node_id: str, kind: str, uid: str, n: int = Query(0),
                        target: str = Query("")):
    """Dispara un enrollment en un nodo (16.22) vía el canal del audio_server (16.21).
    kind = wakeword (muestras de 'Capitán', cross-user) | voice (frases de voz, per-user)."""
    default_n = {"wakeword": 20, "voice": 5, "verify": 1}.get(kind, 5)
    _audio(f"/nodes/{node_id}/enroll", method="POST",
           params={"type": kind, "user_id": uid, "n": n or default_n})
    return HTMLResponse(_enroll_session_fragment(node_id, target))


@app.get("/nodes/{node_id}/enroll/status-fragment", response_class=HTMLResponse)
def node_enroll_status_fragment(node_id: str, target: str = Query("")):
    return HTMLResponse(_enroll_session_fragment(node_id, target))


@app.get("/wakeword", response_class=HTMLResponse)
def wakeword_page(request: Request):
    """Página global de wake word (12.16): entrenamiento transversal + métricas + captura por nodo."""
    train_status = _core("/wakeword/train/status") or {"status": "idle"}
    users = _core("/users") or []
    breakdown = []
    for u in users:
        uid = u.get("id") if isinstance(u, dict) else u
        s = _core(f"/users/{uid}/wakeword/samples") or {"count": 0}
        breakdown.append({"uid": uid, "count": s.get("count", 0)})
    panels = _panels()
    nodes = {n["node_id"]: n for n in (_audio("/nodes") or [])}
    negatives = _audio("/wakeword/negatives") or {}
    return _render(request, "wakeword.html", "wakeword",
                   train_status=train_status, breakdown=breakdown,
                   panels=panels, nodes=nodes, negatives=negatives)


@app.post("/wakeword/train", response_class=HTMLResponse)
def wakeword_train_trigger():
    """Dispara el retrain transversal (12.16). Captura el trained_at previo como baseline
    para distinguir un 'done' NUEVO del último entrenamiento viejo, y polea hasta verlo."""
    baseline = float((_core("/wakeword/train/status") or {}).get("trained_at", 0) or 0)
    _core("/wakeword/train", method="POST", timeout=5)
    return HTMLResponse(_wakeword_train_fragment(baseline=baseline, just_triggered=True))


def _wakeword_train_fragment(baseline: float = 0.0, just_triggered: bool = False) -> str:
    st = _core("/wakeword/train/status") or {"status": "idle"}
    status = st.get("status", "idle")
    trained_at = float(st.get("trained_at", 0) or 0)
    poll = (f'<span hx-get="/wakeword/train/status-fragment?baseline={baseline}" hx-trigger="every 3s"'
            f' hx-target="#train-status" hx-swap="innerHTML"></span>')
    # 'done' sólo cuenta si es NUEVO (posterior al baseline) — evita mostrar el viejo al instante.
    if status == "done" and trained_at > baseline:
        return (f'<p class="text-sm text-emerald-400">✓ entrenado — {st.get("n_positive","?")} positivos / '
                f'{st.get("n_negative","?")} negativos. Los nodos bajan el modelo nuevo solos (≤10 min).</p>')
    if status == "error":
        return f'<p class="text-sm text-red-400">✗ error: {str(st.get("error",""))[:120]}</p>'
    if status == "running" or just_triggered or (status == "done" and trained_at <= baseline):
        return f'<p class="text-sm text-amber-300 animate-pulse">entrenando… (~30-60s)</p>{poll}'
    return '<p class="text-xs text-gray-500">sin entrenar recientemente</p>'


@app.get("/wakeword/train/status-fragment", response_class=HTMLResponse)
def wakeword_train_status_fragment(baseline: float = Query(0)):
    return HTMLResponse(_wakeword_train_fragment(baseline=baseline))


# ── Gestión de paneles (16.26 / Etapa H-I) ────────────────────────────────────

def _save_panels(panels: list[dict]) -> bool:
    """Escribe el registro de paneles (panels.yaml en la raíz del repo)."""
    try:
        import yaml
        p = Path(__file__).parent.parent / "panels.yaml"
        header = ("# Registro de paneles NSPanel Pro (FASE 16.23) — editado desde el backoffice.\n"
                  "# Fuente de verdad del provisioning. Resuelto por nombre/ambiente → IP.\n\n")
        p.write_text(header + yaml.safe_dump({"panels": panels}, allow_unicode=True, sort_keys=False),
                     encoding="utf-8")
        return True
    except Exception:
        return False


@app.get("/panels", response_class=HTMLResponse)
def panels_page(request: Request):
    """Administración de paneles (16.26): lista del registro + estado en vivo del audio_server."""
    panels = _panels()
    nodes = {n["node_id"]: n for n in (_audio("/nodes") or [])}
    return _render(request, "panels.html", "panels", panels=panels, nodes=nodes)


@app.delete("/panels/{name}", response_class=HTMLResponse)
def panels_delete(name: str):
    panels = [p for p in _panels() if p.get("name", "").lower() != name.lower()]
    _save_panels(panels)
    return HTMLResponse("")


# ── Provisioning de panel desde la UI (16.26) ─────────────────────────────────
# Corre scripts/nspanel.sh provision en background; el log se streamea por polling.

_REPO_DIR = Path(__file__).parent.parent
_PROVISION_DIR = Path("/tmp/capitan")


def _provision_log_fragment(name: str) -> str:
    import html as _html
    log = _PROVISION_DIR / f"provision-{name}.log"
    txt = log.read_text(encoding="utf-8", errors="replace")[-4000:] if log.exists() else ""
    done = "completo ===" in txt or "✗" in txt
    poll = "" if done else (f'<span hx-get="/panels/provision/log?name={name}" hx-trigger="every 2s"'
                            f' hx-target="#provision-log" hx-swap="innerHTML"></span>')
    head = ('<p class="text-xs text-emerald-400 mb-1">✓ provisioning terminado</p>' if done
            else '<p class="text-xs text-amber-300 animate-pulse mb-1">provisionando…</p>')
    return (f'{head}<pre class="text-xs bg-black/50 text-gray-300 rounded-lg p-3 overflow-x-auto '
            f'max-h-96 overflow-y-auto whitespace-pre-wrap">{_html.escape(txt) or "iniciando…"}</pre>{poll}')


@app.post("/panels/provision", response_class=HTMLResponse)
async def panels_provision(request: Request):
    form = await request.form()
    name = str(form.get("name", "")).strip().lower()
    room = str(form.get("room", "")).strip().lower() or name
    ip   = str(form.get("ip", "")).strip()
    if not name or not ip:
        return HTMLResponse('<p class="text-red-400 text-xs">Faltan nombre o IP.</p>')
    _PROVISION_DIR.mkdir(parents=True, exist_ok=True)
    log = _PROVISION_DIR / f"provision-{name}.log"
    script = str(_REPO_DIR / "scripts" / "nspanel.sh")
    try:
        f = open(log, "wb")
        subprocess.Popen(["zsh", script, "provision", name, room, ip],
                         stdout=f, stderr=subprocess.STDOUT, cwd=str(_REPO_DIR))
    except Exception as e:
        return HTMLResponse(f'<p class="text-red-400 text-xs">No se pudo lanzar: {e}</p>')
    return HTMLResponse(_provision_log_fragment(name))


@app.get("/panels/provision/log", response_class=HTMLResponse)
def panels_provision_log(name: str):
    return HTMLResponse(_provision_log_fragment(name))


@app.post("/panels/{name}/reboot", response_class=HTMLResponse)
def panels_reboot(name: str):
    """Reinicia un panel vía ADB (16.26)."""
    p = next((x for x in _panels() if str(x.get("name", "")).lower() == name.lower()), None)
    if not p:
        return HTMLResponse('<span class="text-xs text-red-400">panel desconocido</span>')
    ip = p.get("ip", "")
    try:
        subprocess.run(["adb", "connect", f"{ip}:5555"], capture_output=True, timeout=10)
        subprocess.run(["adb", "-s", f"{ip}:5555", "shell", "reboot"], capture_output=True, timeout=10)
        return HTMLResponse('<span class="text-xs text-amber-300">reiniciando… (~30s)</span>')
    except Exception as e:
        return HTMLResponse(f'<span class="text-xs text-red-400">error: {e}</span>')


# Stack legacy de onboarding/enrollment laptop-ear eliminado en 16.29.
# El enrollment es por nodo (audio_server) + página /wakeword + /panels.


# ── RBAC roles ─────────────────────────────────────────────────────────────────

_ROLES_ORDER = ["admin", "familiar", "adolescente", "niño", "invitado", "guest"]


@app.get("/rbac/roles/edit", response_class=HTMLResponse)
def rbac_roles_edit_page(request: Request):
    agents, role_perms = _load_rbac_context()
    return _render(request, "rbac_edit.html", "users",
                   agents=agents, role_perms=role_perms, roles=_ROLES_ORDER, saved=False)


@app.post("/rbac/roles/edit")
async def rbac_roles_save(request: Request):
    form = await request.form()
    agents_data = _core("/agents") or {}
    role_perms = _core("/rbac/roles") or {}
    all_agent_ids = list(agents_data.keys())
    for role in _ROLES_ORDER:
        if role == "admin":
            continue  # admin siempre tiene "*", no se edita
        checked = [aid for aid in all_agent_ids if form.get(f"{role}__{aid}")]
        _core(f"/rbac/roles/{role}", method="PATCH", json={"agents": checked})
    return RedirectResponse("/users", status_code=303)


@app.get("/ear", response_class=HTMLResponse)
def ear_page(request: Request):
    devices = _read_json("devices.json") or {}
    return _render(request, "ear.html", "ear", devices=devices)


@app.get("/devices", response_class=HTMLResponse)
def devices_redirect():
    return RedirectResponse("/ear", status_code=301)


@app.get("/ear/stream")
def ear_stream():
    """SSE: score + estado del ear a ~5Hz."""
    def _gen():
        while True:
            score_data = _read_json("score.json") or {}
            score = round(score_data.get("score", 0.0), 4)
            state_obj = _ear_state()
            state = state_obj.get("state", "stopped") if state_obj else "stopped"
            yield f"data: {json.dumps({'score': score, 'state': state})}\n\n"
            time.sleep(0.2)
    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _speaker_cell(source: dict) -> tuple[str, str]:
    """Devuelve (texto, clase CSS) para mostrar el speaker en tablas."""
    sid  = (source or {}).get("speaker_id") or "?"
    conf = (source or {}).get("speaker_confidence") or 0.0
    if sid == "guest":
        return "guest", "text-gray-600"
    if conf >= 0.80:
        return sid[:10], "text-green-400"
    if conf >= 0.50:
        return sid[:9] + "?", "text-yellow-400"
    return sid[:9] + "?", "text-gray-500"


@app.get("/api/ear/history", response_class=HTMLResponse)
def ear_history_fragment():
    history = _read_json("history.json") or []
    recent  = list(reversed(history[-15:]))
    if not recent:
        return HTMLResponse(
            '<tr><td colspan="6" class="px-3 py-4 text-center text-gray-600">Sin comandos aún</td></tr>'
        )

    def lat_color(v: float) -> str:
        if v <= 0:  return "text-gray-600"
        if v < 10:  return "text-green-400"
        if v < 20:  return "text-yellow-400"
        return "text-red-400"

    rows: list[str] = []
    prev_conv = None
    for e in recent:
        conv_id = e.get("conversation_id") or ""
        if prev_conv is not None and conv_id != prev_conv:
            rows.append('<tr><td colspan="6" class="text-center text-gray-700 py-0.5 text-xs">· · ·</td></tr>')
        accion = e.get("accion") or "—"
        if accion and "→" in accion:
            accion = accion.split("→")[-1].strip()
        lat = e.get("lat_total", 0)
        sp_text, sp_cls = _speaker_cell(e.get("source") or {})
        rows.append(
            f'<tr class="border-b border-gray-800/50 hover:bg-gray-800/30">'
            f'<td class="px-3 py-1.5 text-gray-500 text-xs whitespace-nowrap">{e.get("ts","")}</td>'
            f'<td class="px-3 py-1.5 text-blue-500 text-xs font-mono">{conv_id[:6] or "——"}</td>'
            f'<td class="px-3 py-1.5 {sp_cls} text-xs font-medium">{sp_text}</td>'
            f'<td class="px-3 py-1.5 text-gray-200 text-xs">{e.get("texto","")}</td>'
            f'<td class="px-3 py-1.5 text-cyan-400 text-xs">{accion[:45]}</td>'
            f'<td class="px-3 py-1.5 {lat_color(lat)} text-xs text-right font-mono">{lat:.1f}s</td>'
            f'</tr>'
        )
        prev_conv = conv_id
    return HTMLResponse("\n".join(rows))


@app.get("/api/ear/latency", response_class=HTMLResponse)
def ear_latency_fragment():
    history = _read_json("history.json") or []
    if not history:
        return HTMLResponse('<p class="text-gray-600 text-sm text-center py-3">Sin datos aún</p>')

    last   = history[-1]
    valids = [e for e in history if e.get("lat_total", 0) > 0]

    def avg(k: str) -> float:
        return sum(e.get(k, 0) for e in valids) / len(valids) if valids else 0

    def lat_color(v: float) -> str:
        if v <= 0:  return "text-gray-600"
        if v < 5:   return "text-green-400"
        if v < 10:  return "text-yellow-400"
        return "text-red-400"

    def fmt(v: float) -> str:
        return f"{v:.1f}s" if v > 0 else "—"

    rows: list[str] = []
    for label, key in [("STT (Whisper)", "lat_stt"), ("LLM + HA", "lat_llm"), ("Total", "lat_total")]:
        lv, av = last.get(key, 0), avg(key)
        rows.append(
            f'<div class="flex justify-between items-center py-1.5 border-b border-gray-800/50">'
            f'<span class="text-gray-400 text-sm">{label}</span>'
            f'<div class="flex gap-6">'
            f'<span class="{lat_color(lv)} font-mono text-sm w-12 text-right">{fmt(lv)}</span>'
            f'<span class="text-gray-600 font-mono text-sm w-12 text-right">{fmt(av)}</span>'
            f'</div></div>'
        )
    rows.append(
        f'<div class="flex justify-between items-center pt-2">'
        f'<span class="text-gray-600 text-xs">Comandos (sesión)</span>'
        f'<span class="text-white font-bold">{len(history)}</span>'
        f'</div>'
    )
    return HTMLResponse("\n".join(rows))


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
    core_ok       = _core("/health") is not None
    llm_models = _get_llm_models()
    llm_ok     = bool(llm_models) or _llm_ok()
    ear_state     = _ear_state()

    return _render(request, "integrations.html", "integrations",
                   core_ok=core_ok,
                   core_url=CORE_URL,
                   llm_ok=llm_ok,
                   llm_models=llm_models,
                   ear_state=ear_state)


# ── Plan ───────────────────────────────────────────────────────────────────────

import re as _re
import yaml as _yaml

_GH_DEFAULT_REPO = "mblasi/home-agents"
_TASK_ID_RE = _re.compile(r"^\d+(\.\d+)*$")


def _load_issue_urls() -> dict[str, tuple[str, int]]:
    """Return {task_id: (gh_url, issue_number)} from masterplan/issues.yaml."""
    issues_path = Path.home() / "workspace/home-agents/masterplan/issues.yaml"
    try:
        raw = _yaml.safe_load(issues_path.read_text()) or {}
    except Exception:
        return {}
    urls: dict[str, tuple[str, int]] = {}
    for task_id, v in raw.items():
        task_id = str(task_id)
        if isinstance(v, int):
            urls[task_id] = (f"https://github.com/{_GH_DEFAULT_REPO}/issues/{v}", v)
        elif isinstance(v, dict):
            repo = v.get("repo", _GH_DEFAULT_REPO)
            num  = v.get("number")
            if num:
                urls[task_id] = (f"https://github.com/{repo}/issues/{num}", num)
    return urls


def _parse_plan() -> list[dict]:
    """Parse masterplan/estado.md → phases with per-task detail and GH issue links."""
    plan_path = Path.home() / "workspace/home-agents/masterplan/estado.md"
    try:
        content = plan_path.read_text()
    except Exception:
        return []

    issue_urls = _load_issue_urls()

    phases: list[dict] = []
    current: dict | None = None
    in_code_block = False
    in_masterplan = False

    for line in content.splitlines():
        if line.strip() == "## MASTERPLAN":
            in_masterplan = True
            continue
        if not in_masterplan:
            continue

        if line.startswith("### FASE"):
            if current:
                phases.append(current)
            rest = line[4:].strip()[5:]  # drop "### " then "FASE "
            phase_id, _, title = rest.partition(" - ")
            current = {
                "id": phase_id.strip(),
                "title": title.strip() or phase_id.strip(),
                "objetivo": "",
                "estado_raw": "Pendiente",
                "tasks_done": 0,
                "tasks_total": 0,
                "tasks": [],
            }
            in_code_block = False
            continue

        if current is None:
            continue

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            stripped = line.strip()
            if stripped.startswith("Objetivo:"):
                current["objetivo"] = stripped[9:].strip()
            elif stripped.startswith("Estado:"):
                current["estado_raw"] = stripped[7:].strip()
            continue

        done = None
        if line.startswith("- [x]"):
            done = True
        elif line.startswith("- [ ]"):
            done = False

        if done is not None:
            current["tasks_total"] += 1
            if done:
                current["tasks_done"] += 1
            # Extract task id and text: "- [x] 1.9  Elegir voz..."
            rest = line[6:].strip()
            parts = rest.split(None, 1)
            task_id = parts[0] if parts else ""
            text    = parts[1].strip() if len(parts) > 1 else task_id
            # Strip markdown bold markers
            text = text.replace("**", "")
            # Only treat as linkable id if it looks like N.M[.K...]
            if not _TASK_ID_RE.match(task_id):
                task_id = ""
            gh_url, gh_num = issue_urls.get(task_id, (None, None))
            current["tasks"].append({
                "id":      task_id,
                "text":    text,
                "done":    done,
                "gh_url":  gh_url,
                "gh_num":  gh_num,
            })

    if current:
        phases.append(current)

    for p in phases:
        raw = p["estado_raw"].upper()
        if "COMPLETA" in raw:
            p["estado"] = "COMPLETA"
        elif "EN CURSO" in raw or "PROGRESO" in raw:
            p["estado"] = "EN CURSO"
        else:
            p["estado"] = "Pendiente"
        if p["tasks_total"] > 0:
            p["pct"] = round(100 * p["tasks_done"] / p["tasks_total"])
        else:
            p["pct"] = 100 if p["estado"] == "COMPLETA" else 0

    return phases


@app.get("/plan", response_class=HTMLResponse)
def plan_page(request: Request):
    phases = _parse_plan()
    total_done  = sum(p["tasks_done"]  for p in phases)
    total_tasks = sum(p["tasks_total"] for p in phases)
    total_pct   = round(100 * total_done / total_tasks) if total_tasks else 0
    phases_complete = sum(1 for p in phases if p["estado"] == "COMPLETA")
    return _render(request, "plan.html", "plan",
                   phases=phases, total_done=total_done, total_tasks=total_tasks,
                   total_pct=total_pct, phases_complete=phases_complete)

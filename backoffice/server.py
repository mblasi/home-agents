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

CORE_URL      = os.environ.get("CORE_URL",      "http://localhost:8765")
_LLM_BASE_URL = (os.environ.get("LLM_BASE_URL") or os.environ.get("OLLAMA_URL") or "http://localhost:11434")
BACKOFFICE_TOKEN = os.environ.get("BACKOFFICE_TOKEN", "")
OAUTH_APP_URL = os.environ.get("OAUTH_APP_URL", "").rstrip("/")
METRICS_DIR   = Path("/tmp/capitan")
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="capitan-backoffice", version="1.0")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

import datetime as _dt
def _datetimefmt(ts: float | int) -> str:
    try:
        return _dt.datetime.fromtimestamp(float(ts)).strftime("%d/%m %H:%M")
    except Exception:
        return "—"

templates.env.filters["datetimefmt"] = _datetimefmt

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
    "mp": {
        "me_url": "https://api.mercadopago.com/users/me",
        "label": "MercadoPago",
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
    core_ok = _core("/health", timeout=3) is not None
    data    = _core("/agents", timeout=30) if core_ok else None
    return _render(request, "agents.html", "agents", agents=data or {}, core_ok=core_ok)


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
    kw_raw = str(form.get("keywords", ""))
    keywords = [k.strip() for k in kw_raw.splitlines() if k.strip()]
    payload = {
        "id":            str(form.get("id", "")).strip().lower().replace(" ", "_"),
        "name":          str(form.get("name", "")).strip(),
        "fancy_name":    str(form.get("fancy_name", "")).strip(),
        "icon":          str(form.get("icon", "")).strip(),
        "desc":          str(form.get("desc", "")).strip(),
        "status":        str(form.get("status", "planned")),
        "keywords":      keywords,
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
    return RedirectResponse("/agents", status_code=303)


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

    return _render(request, "agent_edit.html", "agents",
                   agent=agent, agent_id=agent_id, error="",
                   role_perms=role_perms, roles=_ROLES_AGENTS,
                   llm_models=_get_llm_models(),
                   users=users, oauth_statuses=oauth_statuses,
                   just_connected=connected, oauth_error=oauth_error,
                   just_saved=saved, oauth_app_url=OAUTH_APP_URL)


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

    # Keywords: una por línea
    kw_raw = str(form.get("keywords", ""))
    keywords = [k.strip() for k in kw_raw.splitlines() if k.strip()]
    _core(f"/agents/{agent_id}/keywords", method="PATCH", json={"keywords": keywords})

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
def oauth_connect(service: str, user_id: str, agent_id: str = ""):
    """Inicia el flujo OAuth2: pide a core la URL y redirige al usuario."""
    result = _core(f"/auth/{service}/url", params={"user_id": user_id, "agent_id": agent_id})
    if not result or not result.get("url"):
        raise HTTPException(status_code=503, detail=f"Core no pudo generar la URL de autorización para {service}")
    return RedirectResponse(result["url"], status_code=302)


@app.get("/auth/{service}/callback")
def oauth_callback(service: str, code: str = "", state: str = "", error: str = ""):
    """Recibe el callback de ML/MP con el code, lo envía a core para canjearlo."""
    if error or not code:
        return RedirectResponse("/agents", status_code=302)
    result = _core(f"/auth/{service}/callback", method="POST", json={"code": code, "state": state})
    agent_id = (result or {}).get("agent_id", "")
    redirect = f"/agents/{agent_id}/edit?connected=1" if agent_id else "/agents"
    return RedirectResponse(redirect, status_code=302)


@app.post("/auth/{service}/disconnect", response_class=HTMLResponse)
async def oauth_disconnect(request: Request, service: str):
    if service not in _OAUTH_SERVICES:
        raise HTTPException(status_code=404)
    form = await request.form()
    user_id = str(form.get("user_id", "")).strip()
    agent_id = str(form.get("agent_id", "")).strip()
    _oauth_token_path(service, user_id).unlink(missing_ok=True)
    return RedirectResponse(f"/agents/{agent_id}/edit", status_code=303)


@app.post("/auth/{service}/fetch-shortcode")
async def oauth_fetch_shortcode(request: Request, service: str):
    """Recupera el token del oauth app por short_code y lo persiste localmente."""
    form = await request.form()
    user_id  = str(form.get("user_id", "")).strip()
    agent_id = str(form.get("agent_id", "")).strip()

    def _err(msg: str):
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
    redirect = f"/agents/{agent_id}/edit?connected=1" if agent_id else "/agents"
    return RedirectResponse(redirect, status_code=303)


@app.post("/auth/{service}/set-token")
async def oauth_set_token(request: Request, service: str):
    """Configura tokens OAuth manualmente, como fallback al circuito WA."""
    form = await request.form()
    user_id       = str(form.get("user_id", "")).strip()
    agent_id      = str(form.get("agent_id", "")).strip()
    access_token  = str(form.get("access_token", "")).strip()
    refresh_token = str(form.get("refresh_token", "")).strip()

    def _err(msg: str):
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
    redirect = f"/agents/{agent_id}/edit?connected=1" if agent_id else "/agents"
    return RedirectResponse(redirect, status_code=303)


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
    return RedirectResponse(f"/users/{uid}/onboard", status_code=303)


@app.get("/users/{uid}", response_class=HTMLResponse)
def user_detail_page(request: Request, uid: str):
    user = _core(f"/users/{uid}")
    if not user:
        return RedirectResponse("/users", status_code=303)
    agents, _ = _load_rbac_context()
    ww_samples   = _core(f"/users/{uid}/wakeword/samples") or {"count": 0, "required": 30, "samples": []}
    ww_metrics   = _core(f"/users/{uid}/wakeword/metrics") or {"tp": 0, "fp": 0, "rbac_deny": 0}
    train_status = _core("/wakeword/train/status") or {"status": "idle"}
    user_context     = _core(f"/users/{uid}/context/raw") or {}
    user_intents     = _core(f"/users/{uid}/intents", params={"active_only": True}) or []
    proactive_status = _core("/proactive/status", timeout=3) or {}
    # proactive_enabled per agent from plain context (not raw)
    user_ctx_plain   = _core(f"/users/{uid}/context") or {}
    return _render(request, "user_detail.html", "users",
                   user=user, uid=uid, agents=agents,
                   ww_samples=ww_samples, ww_metrics=ww_metrics,
                   train_status=train_status,
                   user_context=user_context, user_intents=user_intents,
                   proactive_status=proactive_status,
                   user_ctx_plain=user_ctx_plain)


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

_ENROLL_LABELS = {
    "frases_speaker_id":  ("Identificación de voz", 5),
    "muestras_wake_word": ("Muestras de wake word", 30),
}
_NEXT_STEP = {
    "frases_speaker_id":  "muestras_wake_word",
    "muestras_wake_word": "completo",
}


def _enroll_fragment(uid: str, sid: str, progress: int, total: int, status: str, step: str) -> str:
    label = _ENROLL_LABELS.get(step, (step, total))[0]
    pct = int(progress / total * 100) if total else 0

    if status == "pending":
        body = (
            '<p class="text-gray-400 text-sm animate-pulse">Esperando al dispositivo ear…</p>'
            f'<span hx-get="/users/{uid}/enroll/status/{sid}"'
            f' hx-trigger="every 2s" hx-target="#enroll-fragment" hx-swap="innerHTML"></span>'
        )
    elif status == "in_progress":
        body = (
            f'<p class="text-sm text-gray-300 mb-2">{label}: {progress}/{total}</p>'
            f'<div class="w-full bg-gray-700 rounded-full h-2 mb-1">'
            f'  <div class="bg-blue-500 h-2 rounded-full transition-all" style="width:{pct}%"></div>'
            f'</div>'
            f'<p class="text-xs text-gray-500">{pct}%</p>'
            f'<span hx-get="/users/{uid}/enroll/status/{sid}"'
            f' hx-trigger="every 2s" hx-target="#enroll-fragment" hx-swap="innerHTML"></span>'
        )
    elif status == "done":
        next_step = _NEXT_STEP.get(step, "completo")
        if next_step == "completo":
            next_html = (
                '<a href="/users" class="text-emerald-400 underline text-sm">Ver usuarios</a>'
            )
        else:
            next_label = _ENROLL_LABELS.get(next_step, (next_step,))[0]
            next_html = (
                f'<a href="/users/{uid}/onboard" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 '
                f'text-white rounded-lg text-xs font-medium">Continuar → {next_label}</a>'
            )
        body = (
            f'<p class="text-emerald-400 text-sm font-medium mb-3">✓ {label} completado ({progress}/{total})</p>'
            + next_html
        )
    elif status in ("cancelled", "error"):
        body = f'<p class="text-red-400 text-sm">✗ {status.capitalize()} — recargá la página para reintentar.</p>'
    else:
        body = f'<p class="text-gray-500 text-xs">{status}</p>'

    return body


@app.get("/users/{uid}/onboard", response_class=HTMLResponse)
def user_onboard_page(request: Request, uid: str):
    user = _core(f"/users/{uid}")
    if not user:
        return RedirectResponse("/users", status_code=303)
    step = user.get("onboarding_step", "completo")
    return _render(request, "user_onboard.html", "users",
                   user=user, uid=uid, step=step,
                   enroll_labels=_ENROLL_LABELS, next_step=_NEXT_STEP)


@app.post("/users/{uid}/enroll/start", response_class=HTMLResponse)
async def start_enroll(uid: str, request: Request):
    form = await request.form()
    step = str(form.get("step", ""))
    if step not in _ENROLL_LABELS:
        return HTMLResponse('<p class="text-red-400 text-xs">Paso inválido</p>')
    result = _core("/enrollment/sessions", method="POST", json={"user_id": uid, "step": step})
    if not result:
        return HTMLResponse('<p class="text-red-400 text-xs">El core no está disponible</p>')
    sid = result["session_id"]
    total = result["total"]
    return HTMLResponse(_enroll_fragment(uid, sid, 0, total, "pending", step))


@app.get("/users/{uid}/enroll/status/{sid}", response_class=HTMLResponse)
def enroll_status_fragment(uid: str, sid: str):
    session = _core(f"/enrollment/sessions/{sid}")
    if not session:
        return HTMLResponse('<p class="text-red-400 text-xs">Sesión expirada o no encontrada</p>')
    return HTMLResponse(_enroll_fragment(
        uid, sid,
        session.get("progress", 0),
        session.get("total", 1),
        session.get("status", "pending"),
        session.get("step", ""),
    ))


_POLLING_SPAN = (
    '<span class="text-blue-400 text-xs animate-pulse"'
    ' hx-get="/wakeword/train/status"'
    ' hx-trigger="every 3s"'
    ' hx-target="#train-status"'
    ' hx-swap="innerHTML">⟳ Entrenando…</span>'
)


@app.post("/wakeword/train/start", response_class=HTMLResponse)
def start_wakeword_train():
    """Proxy para lanzar reentrenamiento desde el backoffice (HTMX)."""
    result = _core("/wakeword/train", method="POST") or {}
    status = result.get("status", "error")
    if status == "started":
        return HTMLResponse(_POLLING_SPAN)
    elif status == "conflict":
        return HTMLResponse('<span class="text-orange-400 text-xs">Ya hay un entrenamiento en curso</span>')
    return HTMLResponse('<span class="text-red-400 text-xs">Error al iniciar entrenamiento</span>')


@app.get("/wakeword/train/status", response_class=HTMLResponse)
def wakeword_train_status_fragment():
    """Fragmento HTMX (innerHTML de #train-status) con el estado actual del entrenamiento."""
    result = _core("/wakeword/train/status") or {"status": "idle"}
    status = result.get("status", "idle")
    if status == "running":
        return HTMLResponse(_POLLING_SPAN)
    elif status == "done":
        n_pos = result.get("n_positive", "?")
        n_real = result.get("n_positive_real", 0)
        dur = result.get("duration_s", "?")
        return HTMLResponse(
            f'<span class="text-emerald-400 text-xs">✓ Listo — {n_pos} positivos ({n_real} reales), {dur}s</span>'
        )
    elif status == "error":
        err = result.get("error", "desconocido")
        return HTMLResponse(f'<span class="text-red-400 text-xs">✗ Error: {err[:60]}</span>')
    return HTMLResponse('<span class="text-gray-600 text-xs">Sin entrenamientos recientes</span>')


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

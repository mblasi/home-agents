"""Backoffice en la nube — Cloud Run + Firestore. FASE 33 Etapa B.

Patrón command/executor con control por inversión: el SER9 empuja estado (ingest)
y polea comandos (pending) — todas conexiones SALIENTES desde la casa. La nube
nunca inicia conexiones hacia el SER9.
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from starlette.middleware.base import BaseHTTPMiddleware

from . import firestore_db as fdb
from . import ratelimit
from .auth import ALLOWED_EMAILS, FIREBASE_PROJECT_ID, require_bridge, require_dashboard_user
from .commands import CommandError, catalog_summary, validate_command
from .models import SCHEMA_VERSION, CommandRequest, CommandResult, StateSnapshot

HERE = os.path.dirname(__file__)
MAX_BODY = int(os.environ.get("MAX_BODY_BYTES", str(512 * 1024)))  # 512 KB

app = FastAPI(title="home-agents cloud backoffice", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))


class BodySizeLimit(BaseHTTPMiddleware):
    """Rechaza payloads grandes antes de parsearlos (33.14)."""
    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY:
            return JSONResponse({"detail": "payload demasiado grande"}, status_code=413)
        return await call_next(request)


app.add_middleware(BodySizeLimit)


@app.get("/_health")
def health():
    # /healthz lo reserva el Google Front End en Cloud Run; usar /_health.
    return {"ok": True}


# ── Bridge (SER9 → nube): conexiones salientes, auth OIDC de la SA ──────────────

@app.post("/ingest/state")
def ingest_state(snapshot: StateSnapshot, sa: str = Depends(require_bridge)):
    ratelimit.limit_ingest(sa)
    if snapshot.schema_version != SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail="schema_version no soportada")
    fdb.store_state(snapshot.model_dump())
    return {"ok": True}


@app.get("/commands/pending")
def commands_pending(sa: str = Depends(require_bridge)):
    ratelimit.limit_ingest(sa)
    return {"commands": fdb.claim_pending()}


@app.post("/commands/{cmd_id}/result")
def command_result(cmd_id: str, result: CommandResult, sa: str = Depends(require_bridge)):
    if not fdb.set_result(cmd_id, result.ok, result.output, result.error):
        raise HTTPException(status_code=404, detail="comando inexistente")
    return {"ok": True}


# ── Dashboard API (navegador → nube): auth Firebase + allow-list de email ───────

@app.get("/api/state")
def api_state(user: str = Depends(require_dashboard_user)):
    state = fdb.get_state()
    if state is None:
        return JSONResponse({"state": None}, status_code=200)
    return {"state": state}


@app.get("/api/commands")
def api_commands(user: str = Depends(require_dashboard_user)):
    return {"commands": fdb.recent_commands()}


@app.get("/api/catalog")
def api_catalog(user: str = Depends(require_dashboard_user)):
    return {"catalog": catalog_summary()}


@app.post("/api/commands")
def api_emit_command(req: CommandRequest, user: str = Depends(require_dashboard_user)):
    ratelimit.limit_command(user)
    try:
        params = validate_command(req.type, req.params)
    except CommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cmd = fdb.enqueue_command(req.type, params, issued_by=user)
    return {"command": cmd}


# ── Frontend ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "firebase_api_key": os.environ.get("FIREBASE_API_KEY", ""),
        "firebase_auth_domain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
        "firebase_project_id": FIREBASE_PROJECT_ID,
        "allowed_emails": ", ".join(sorted(ALLOWED_EMAILS)),
    })

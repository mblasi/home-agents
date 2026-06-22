"""Backoffice en la nube — Cloud Run + Firestore. FASE 33 Etapa B.

Patrón command/executor con control por inversión: el Brain empuja estado (ingest)
y polea comandos (pending) — todas conexiones SALIENTES desde la casa. La nube
nunca inicia conexiones hacia el Brain.
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
from . import rbac
from . import sso
from .auth import (
    ALLOWED_EMAILS,
    FIREBASE_PROJECT_ID,
    Principal,
    require_bridge,
    require_dashboard_user,
)
from .commands import CommandError, catalog_summary, validate_command
from .models import (
    METRICS_SCHEMA_VERSION,
    SCHEMA_VERSION,
    CommandProgress,
    CommandRequest,
    CommandResult,
    MetricsSnapshot,
    StateSnapshot,
)

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


# ── Bridge (Brain → nube): conexiones salientes, auth OIDC de la SA ──────────────

@app.post("/ingest/state")
def ingest_state(snapshot: StateSnapshot, sa: str = Depends(require_bridge)):
    ratelimit.limit_ingest(sa)
    if snapshot.schema_version != SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail="schema_version no soportada")
    data = snapshot.model_dump()
    fdb.store_state(data)
    # Materializa el roster email→rol para autorizar el login del dashboard (33.19).
    fdb.store_roster(data.get("users_summary", []))
    return {"ok": True}


@app.post("/ingest/metrics")
def ingest_metrics(snapshot: MetricsSnapshot, sa: str = Depends(require_bridge)):
    """Recibe agregados de métricas del bridge (FASE 35.5). Egress-only: el Brain
    empuja, la nube almacena."""
    ratelimit.limit_ingest(sa)
    if snapshot.schema_version != METRICS_SCHEMA_VERSION:
        raise HTTPException(status_code=422, detail="schema_version no soportada")
    fdb.store_metrics(snapshot.model_dump())
    return {"ok": True}


@app.get("/commands/pending")
def commands_pending(sa: str = Depends(require_bridge)):
    ratelimit.limit_ingest(sa)
    return {"commands": fdb.claim_pending()}


@app.post("/commands/{cmd_id}/progress")
def command_progress(cmd_id: str, prog: CommandProgress, sa: str = Depends(require_bridge)):
    """D5: el bridge postea líneas de log en vivo mientras ejecuta un comando largo (deploy)."""
    ratelimit.limit_ingest(sa)
    if not fdb.append_progress(cmd_id, prog.lines):
        raise HTTPException(status_code=404, detail="comando inexistente")
    return {"ok": True}


@app.post("/commands/{cmd_id}/result")
def command_result(cmd_id: str, result: CommandResult, sa: str = Depends(require_bridge)):
    if not fdb.set_result(cmd_id, result.ok, result.output, result.error):
        raise HTTPException(status_code=404, detail="comando inexistente")
    return {"ok": True}


# ── Dashboard API (navegador → nube): auth Firebase + roster + RBAC ─────────────

def _require_emit(p: Principal) -> None:
    if not p.caps.get("emit"):
        raise HTTPException(status_code=403, detail="tu rol no puede emitir comandos")


def _require_view_full(p: Principal) -> None:
    if not p.caps.get("view_full"):
        raise HTTPException(status_code=403, detail="tu rol no tiene acceso a esta vista")


@app.get("/api/me")
def api_me(p: Principal = Depends(require_dashboard_user)):
    return {"email": p.email, "role": p.role, "caps": p.caps}


@app.get("/api/state")
def api_state(p: Principal = Depends(require_dashboard_user)):
    state = fdb.get_state()
    if state is None:
        return JSONResponse({"state": None}, status_code=200)
    return {"state": rbac.filter_state(state, p.caps)}


@app.get("/api/metrics")
def api_metrics(p: Principal = Depends(require_dashboard_user)):
    """Métricas para el dashboard cloud (FASE 35.6), filtradas por RBAC."""
    metrics = fdb.get_metrics()
    if metrics is None:
        return JSONResponse({"metrics": None}, status_code=200)
    return {"metrics": rbac.filter_metrics(metrics, p.caps)}


@app.get("/api/commands")
def api_commands(p: Principal = Depends(require_dashboard_user)):
    _require_view_full(p)  # la auditoría sólo para roles con view_full
    return {"commands": fdb.recent_commands()}


@app.get("/api/commands/{cmd_id}")
def api_command(cmd_id: str, p: Principal = Depends(require_dashboard_user)):
    """D5: el dashboard polea un comando para ver su progreso/estado en vivo durante el deploy."""
    _require_view_full(p)
    cmd = fdb.get_command(cmd_id)
    if not cmd:
        raise HTTPException(status_code=404, detail="comando inexistente")
    return {"command": cmd}


@app.get("/api/catalog")
def api_catalog(p: Principal = Depends(require_dashboard_user)):
    _require_emit(p)
    return {"catalog": catalog_summary()}


@app.get("/api/alerts")
def api_alerts(p: Principal = Depends(require_dashboard_user)):
    """Alertas proactivas vigentes (FASE 37.6). Viajan en el snapshot (37.1/37.7); este
    endpoint las expone aisladas para la sección Alertas. Gated por `access`."""
    state = fdb.get_state()
    alerts = (state or {}).get("alerts", []) if state else []
    return {"alerts": alerts}


# Tipos de comando que producen logs poleables por la sección Logs (37.6/37.10).
_LOG_COMMANDS = ("logs.tail", "logs.satellite")


@app.get("/api/logs")
def api_logs(p: Principal = Depends(require_dashboard_user)):
    """Último resultado de un comando de logs (poll del resultado de logs.tail). El front emite
    el comando y luego polea acá el output ya ejecutado por el bridge. Gated por `emit`."""
    _require_emit(p)
    for c in fdb.recent_commands(limit=50):
        if c.get("type") in _LOG_COMMANDS:
            return {"log": c}
    return {"log": None}


@app.post("/api/commands")
def api_emit_command(req: CommandRequest, p: Principal = Depends(require_dashboard_user)):
    _require_emit(p)
    ratelimit.limit_command(p.email)
    try:
        params = validate_command(req.type, req.params)
    except CommandError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cmd = fdb.enqueue_command(req.type, params, issued_by=p.email)
    return {"command": cmd}


# ── SSO broker para el backoffice local (33.22) ─────────────────────────────────

LOCAL_SSO_ORIGINS = {
    o.strip().rstrip("/")
    for o in os.environ.get("LOCAL_SSO_ORIGINS", "").split(",") if o.strip()
}


def _valid_redirect(redirect_uri: str) -> bool:
    """El redirect_uri debe ser /sso/callback de un origen LAN permitido."""
    try:
        from urllib.parse import urlparse
        u = urlparse(redirect_uri)
        origin = f"{u.scheme}://{u.netloc}"
        return origin in LOCAL_SSO_ORIGINS and u.path == "/sso/callback"
    except Exception:  # noqa: BLE001
        return False


@app.get("/sso/start", response_class=HTMLResponse)
def sso_start(request: Request, redirect_uri: str = ""):
    if not _valid_redirect(redirect_uri):
        raise HTTPException(status_code=400, detail="redirect_uri no permitido")
    return templates.TemplateResponse(request, "sso.html", {
        "firebase_api_key": os.environ.get("FIREBASE_API_KEY", ""),
        "firebase_auth_domain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
        "firebase_project_id": FIREBASE_PROJECT_ID,
        "redirect_uri": redirect_uri,
    })


@app.post("/sso/mint")
def sso_mint(body: dict, p: Principal = Depends(require_dashboard_user)):
    redirect_uri = (body or {}).get("redirect_uri", "")
    if not _valid_redirect(redirect_uri):
        raise HTTPException(status_code=400, detail="redirect_uri no permitido")
    token = sso.mint(p.email, p.role)
    return {"redirect": f"{redirect_uri}?sso={token}"}


# ── Frontend ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html", {
        "firebase_api_key": os.environ.get("FIREBASE_API_KEY", ""),
        "firebase_auth_domain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
        "firebase_project_id": FIREBASE_PROJECT_ID,
        "allowed_emails": ", ".join(sorted(ALLOWED_EMAILS)),
    })

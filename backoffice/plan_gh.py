"""Plan de desarrollo a partir de los issues de GitHub (issue #766).

Fuente de verdad del plan: los issues. Cada issue de una tarea lleva un label `fase-N` (cuya
descripción es el título de la fase); el estado de la tarea es el del issue (open/closed). El
título del issue empieza con el id de tarea (`[39.1] ...` o `39.1 ...`).

- `get_plan()` consulta la API REST de GitHub (opcional `GITHUB_TOKEN` en backoffice/.env para
  el rate limit) con caché en memoria (`CACHE_TTL`). Si GitHub falla devuelve el último plan
  cacheado marcado `stale`; sin caché, devuelve `phases=[]` y el error para que la página avise.
- Los issues abiertos sin label `fase-N` se muestran en un grupo final "Sin fase".
"""
from __future__ import annotations

import os
import re
import threading
import time

import requests

REPOS = ["mblasi/home-agents", "mblasi/home-agents-core", "mblasi/home-agents-ear"]
API = "https://api.github.com"
PAGE_SIZE = 100
CACHE_TTL = 300        # s — un issue cerrado se refleja en la página en <= 5 min
RETRY_AFTER_FAIL = 60  # s — no martillar a GitHub si falló
HTTP_TIMEOUT = 15

PHASE_LABEL_PREFIX = "fase-"
WIP_LABEL = "status:wip"
NO_PHASE_ID = "—"
NO_PHASE_TITLE = "Sin fase"

_TITLE_RE = re.compile(r"^\s*\[?(\d+(?:\.\d+)*)\]?\s*[—–-]?\s*(.*)$")

_lock = threading.Lock()
_cache: dict = {"data": None, "at": 0.0, "failed_at": 0.0, "error": None}


def clear_cache() -> None:
    with _lock:
        _cache.update(data=None, at=0.0, failed_at=0.0, error=None)


def parse_title(title: str) -> tuple[str, str]:
    """'[39.1] Texto' / '34.17 — Texto' → ('39.1', 'Texto'); sin id → ('', title)."""
    m = _TITLE_RE.match(title or "")
    if not m or not m.group(2):
        return "", (title or "").strip()
    return m.group(1), m.group(2).strip()


def _num_key(s: str) -> tuple:
    """Orden natural de ids '3.5' < '10' < '39.10'; vacío al final."""
    if not s:
        return (1, ())
    return (0, tuple(int(p) for p in s.split(".") if p.isdigit()))


def _phase_of(issue: dict) -> tuple[str | None, str | None]:
    for lb in issue.get("labels", []):
        name = lb.get("name", "")
        if name.startswith(PHASE_LABEL_PREFIX):
            return name[len(PHASE_LABEL_PREFIX):], lb.get("description") or None
    return None, None


def build_phases(issues: list[dict]) -> list[dict]:
    """Agrupa issues (formato de la API REST) en fases con tareas y progreso."""
    phases: dict[str, dict] = {}
    for it in issues:
        if "pull_request" in it:
            continue
        done = it.get("state") == "closed"
        pid, desc = _phase_of(it)
        if pid is None:
            if done:
                continue
            pid, desc = NO_PHASE_ID, NO_PHASE_TITLE
        p = phases.setdefault(pid, {
            "id": pid, "title": None, "tasks": [], "wip": False,
        })
        if desc and not p["title"]:
            p["title"] = desc
        if any(lb.get("name") == WIP_LABEL for lb in it.get("labels", [])):
            p["wip"] = True
        tid, text = parse_title(it.get("title", ""))
        p["tasks"].append({
            "id": tid, "text": text, "done": done,
            "gh_num": it.get("number"), "gh_url": it.get("html_url"),
        })

    out = []
    for p in phases.values():
        p["tasks"].sort(key=lambda t: (_num_key(t["id"]), t["gh_num"] or 0))
        total = len(p["tasks"])
        done = sum(1 for t in p["tasks"] if t["done"])
        wip = p.pop("wip")
        if total and done == total:
            estado = "COMPLETA"
        elif done or wip:
            estado = "EN CURSO"
        else:
            estado = "Pendiente"
        p.update(
            title=p["title"] or f"FASE {p['id']}",
            tasks_total=total, tasks_done=done, estado=estado,
            pct=round(100 * done / total) if total else 0,
        )
        out.append(p)
    out.sort(key=lambda p: (p["id"] == NO_PHASE_ID, _num_key(p["id"])))
    return out


def summarize(phases: list[dict]) -> dict:
    """Totales globales (el grupo 'Sin fase' no cuenta para el progreso)."""
    real = [p for p in phases if p["id"] != NO_PHASE_ID]
    done = sum(p["tasks_done"] for p in real)
    total = sum(p["tasks_total"] for p in real)
    return {
        "total_done": done,
        "total_tasks": total,
        "total_pct": round(100 * done / total) if total else 0,
        "phases_complete": sum(1 for p in real if p["estado"] == "COMPLETA"),
        "phases_total": len(real),
    }


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _fetch_issues() -> list[dict]:
    issues: list[dict] = []
    for repo in REPOS:
        page = 1
        while True:
            r = requests.get(
                f"{API}/repos/{repo}/issues",
                params={"state": "all", "per_page": PAGE_SIZE, "page": page},
                headers=_headers(), timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            batch = r.json()
            issues.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            page += 1
    return issues


def get_plan() -> dict:
    """{'phases': [...], 'error': str|None, 'stale': bool}. Nunca lanza."""
    with _lock:
        now = time.time()
        if _cache["data"] is not None and now - _cache["at"] < CACHE_TTL:
            return {"phases": _cache["data"], "error": None, "stale": False}
        if _cache["failed_at"] and now - _cache["failed_at"] < RETRY_AFTER_FAIL:
            return {"phases": _cache["data"] or [], "error": _cache["error"],
                    "stale": _cache["data"] is not None}
        try:
            phases = build_phases(_fetch_issues())
        except Exception as e:  # noqa: BLE001 — degradación elegante ante cualquier falla
            _cache.update(failed_at=now, error=str(e) or type(e).__name__)
            return {"phases": _cache["data"] or [], "error": _cache["error"],
                    "stale": _cache["data"] is not None}
        _cache.update(data=phases, at=now, failed_at=0.0, error=None)
        return {"phases": phases, "error": None, "stale": False}

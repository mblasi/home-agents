"""Acceso a Firestore: snapshot de estado + cola de comandos. Ver 33.6.

Colecciones:
- state/current        : último snapshot recibido.
- state_history/{id}   : histórico corto (TTL via campo expires_at).
- commands/{id}        : cola de comandos (pending|running|done|error, TTL ttl_at).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

# google.cloud.firestore se importa de forma lazy (dentro de las funciones) para no
# forzar esa dependencia pesada en tests de unidad de otros módulos.

HISTORY_TTL_HOURS = int(os.environ.get("STATE_HISTORY_TTL_HOURS", "24"))
COMMAND_TTL_HOURS = int(os.environ.get("COMMAND_TTL_HOURS", "24"))

_client = None


def db():
    global _client
    if _client is None:
        from google.cloud import firestore
        _client = firestore.Client()
    return _client


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Estado ────────────────────────────────────────────────────────────────────

def store_state(snapshot: dict) -> None:
    received = _now()
    doc = {**snapshot, "received_at": received}
    db().collection("state").document("current").set(doc)
    hist = {**doc, "expires_at": received + timedelta(hours=HISTORY_TTL_HOURS)}
    db().collection("state_history").document(received.strftime("%Y%m%dT%H%M%S%f")).set(hist)


def get_state() -> dict | None:
    snap = db().collection("state").document("current").get()
    return snap.to_dict() if snap.exists else None


# ── Métricas (FASE 35.5) ────────────────────────────────────────────────────────

def store_metrics(snapshot: dict) -> None:
    received = _now()
    doc = {**snapshot, "received_at": received}
    db().collection("metrics").document("current").set(doc)
    hist = {**doc, "expires_at": received + timedelta(hours=HISTORY_TTL_HOURS)}
    db().collection("metrics_history").document(received.strftime("%Y%m%dT%H%M%S%f")).set(hist)


def get_metrics() -> dict | None:
    snap = db().collection("metrics").document("current").get()
    return snap.to_dict() if snap.exists else None


# ── Roster de autorización (email→rol), materializado desde el snapshot ─────────

def store_roster(users_summary: list[dict]) -> None:
    """Materializa el roster email→rol para autorizar el login del dashboard.
    Se guarda como lista (las field keys de Firestore no admiten '.' del email)."""
    entries = [
        {"email": u["email"].strip().lower(), "role": u.get("role", "")}
        for u in users_summary
        if u.get("email")
    ]
    db().collection("auth").document("roster").set(
        {"entries": entries, "updated_at": _now()}
    )


def get_roster() -> dict[str, str]:
    snap = db().collection("auth").document("roster").get()
    if not snap.exists:
        return {}
    return {e["email"]: e.get("role", "") for e in snap.to_dict().get("entries", [])}


# ── Comandos ──────────────────────────────────────────────────────────────────

def enqueue_command(cmd_type: str, params: dict, issued_by: str) -> dict:
    now = _now()
    cmd = {
        "id": f"cmd_{uuid.uuid4().hex[:24]}",
        "type": cmd_type,
        "params": params,
        "issued_by": issued_by,
        "issued_at": now.isoformat(),
        "status": "pending",
        "result": None,
        "ttl_at": now + timedelta(hours=COMMAND_TTL_HOURS),
    }
    db().collection("commands").document(cmd["id"]).set(cmd)
    return cmd


def claim_pending(limit: int = 20) -> list[dict]:
    """Devuelve comandos pending y los pasa a running atómicamente (evita doble
    ejecución entre ciclos de polling del bridge)."""
    from google.cloud import firestore
    col = db().collection("commands")
    q = col.where("status", "==", "pending").limit(limit)
    claimed: list[dict] = []
    for snap in q.stream():
        ref = col.document(snap.id)

        @firestore.transactional
        def _claim(tx, ref=ref):
            cur = ref.get(transaction=tx).to_dict()
            if not cur or cur.get("status") != "pending":
                return None
            cur["status"] = "running"
            cur["claimed_at"] = _now().isoformat()
            tx.set(ref, cur)
            return cur

        cur = _claim(db().transaction())
        if cur:
            claimed.append(cur)
    return claimed


def set_result(cmd_id: str, ok: bool, output: str, error: str) -> bool:
    ref = db().collection("commands").document(cmd_id)
    snap = ref.get()
    if not snap.exists:
        return False
    ref.update({
        "status": "done" if ok else "error",
        "result": {"ok": ok, "output": output[:8000], "error": error[:2000]},
        "finished_at": _now().isoformat(),
    })
    return True


def recent_commands(limit: int = 50) -> list[dict]:
    from google.cloud import firestore
    col = db().collection("commands")
    q = col.order_by("issued_at", direction=firestore.Query.DESCENDING).limit(limit)
    return [snap.to_dict() for snap in q.stream()]

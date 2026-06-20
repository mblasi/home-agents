#!/usr/bin/env python3
"""cloud_bridge.py — bridge/executor del SER9 hacia el backoffice en la nube.

FASE 33 Etapa C. Conexiones SALIENTES únicamente (control por inversión):
  - push periódico del snapshot de estado    → POST /ingest/state          (33.10)
  - poll de la cola de comandos con backoff   → GET  /commands/pending      (33.11)
  - ejecuta cada comando (executor seguro)    → POST /commands/{id}/result  (33.12)

Auth: ID token OIDC de la Service Account del bridge (audience = URL del servicio),
sin API keys embebidas. La key de la SA vive FUERA del repo (33.13).
"""
from __future__ import annotations

import logging
import os
import sys
import time

# Catálogo TIPADO compartido con la nube (única fuente de verdad).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.commands import CommandError, validate_command  # noqa: E402

from google.auth.transport.requests import AuthorizedSession  # noqa: E402
from google.oauth2 import service_account  # noqa: E402

import executor  # noqa: E402
import metrics_snapshot  # noqa: E402
import snapshot  # noqa: E402

CLOUD_URL = os.environ["CLOUD_URL"].rstrip("/")
SA_KEY = os.environ["BRIDGE_SA_KEY"]
PUSH_INTERVAL = int(os.environ.get("PUSH_INTERVAL", "30"))
METRICS_PUSH_INTERVAL = int(os.environ.get("METRICS_PUSH_INTERVAL", "300"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "10"))
MAX_BACKOFF = int(os.environ.get("MAX_BACKOFF", "300"))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cloud_bridge")


def _session() -> AuthorizedSession:
    creds = service_account.IDTokenCredentials.from_service_account_file(
        SA_KEY, target_audience=CLOUD_URL,
    )
    return AuthorizedSession(creds)


def push_state(sess: AuthorizedSession) -> None:
    snap = snapshot.build_snapshot()
    r = sess.post(f"{CLOUD_URL}/ingest/state", json=snap, timeout=15)
    r.raise_for_status()
    log.info("push estado OK (%d servicios, %d agentes)",
             len(snap["services"]), len(snap["agents"]))


def push_metrics(sess: AuthorizedSession) -> None:
    snap = metrics_snapshot.build_metrics_snapshot()
    r = sess.post(f"{CLOUD_URL}/ingest/metrics", json=snap, timeout=20)
    r.raise_for_status()
    log.info("push métricas OK (ventana %dh)", snap.get("window_hours"))


# Cada cuántas líneas de progreso se hace un POST al cloud (batch para no spamear Firestore).
PROGRESS_BATCH = int(os.environ.get("PROGRESS_BATCH", "5"))


def _progress_emitter(sess: AuthorizedSession, cid: str):
    """Devuelve un callback `emit(line)` que acumula líneas de log del comando y las postea en
    lotes a /commands/{id}/progress (D5: logs en vivo). Best-effort: un fallo de red al postear
    progreso NO interrumpe la ejecución del comando (el resultado final igual se reporta)."""
    buf: list[str] = []

    def _flush() -> None:
        if not buf:
            return
        try:
            # Copia: el buffer se vacía a continuación; no compartir la referencia con el POST.
            sess.post(f"{CLOUD_URL}/commands/{cid}/progress",
                      json={"lines": list(buf)}, timeout=10)
        except Exception as exc:  # noqa: BLE001
            log.warning("no se pudo postear progreso de %s: %s", cid, exc)
        buf.clear()

    def emit(line: str) -> None:
        buf.append(line)
        if len(buf) >= PROGRESS_BATCH:
            _flush()

    emit.flush = _flush  # type: ignore[attr-defined]
    return emit


def poll_and_execute(sess: AuthorizedSession) -> None:
    r = sess.get(f"{CLOUD_URL}/commands/pending", timeout=15)
    r.raise_for_status()
    for cmd in r.json().get("commands", []):
        cid, ctype, params = cmd["id"], cmd["type"], cmd.get("params", {})
        log.info("comando %s type=%s params=%s issued_by=%s",
                 cid, ctype, params, cmd.get("issued_by"))
        emit = _progress_emitter(sess, cid)
        try:
            clean = validate_command(ctype, params)  # re-validación defensiva
            result = executor.execute(ctype, clean, emit=emit)
        except CommandError as exc:
            result = executor.ExecResult(False, "", f"rechazado por catálogo: {exc}")
        emit.flush()  # vaciar el último lote de progreso antes del resultado
        log.info("comando %s → ok=%s %s", cid, result.ok, result.error or "")
        try:
            rr = sess.post(f"{CLOUD_URL}/commands/{cid}/result",
                           json=result.as_dict(), timeout=15)
            rr.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.error("no se pudo postear resultado de %s: %s", cid, exc)


def main() -> None:
    log.info("bridge arrancando → %s (push %ds, poll %ds)",
             CLOUD_URL, PUSH_INTERVAL, POLL_INTERVAL)
    sess = _session()
    last_push = 0.0
    last_metrics_push = 0.0
    backoff = POLL_INTERVAL
    while True:
        try:
            now = time.monotonic()
            if now - last_push >= PUSH_INTERVAL:
                push_state(sess)
                last_push = now
            if now - last_metrics_push >= METRICS_PUSH_INTERVAL:
                push_metrics(sess)
                last_metrics_push = now
            poll_and_execute(sess)
            backoff = POLL_INTERVAL  # reset tras un ciclo OK
        except Exception as exc:  # noqa: BLE001 — la nube puede estar caída
            log.warning("ciclo falló (%s); backoff %ds", exc, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            continue
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

"""Construcción del snapshot de métricas (SER9 → nube). FASE 35.5.

Lee los agregados ya calculados por el core (API de métricas de FASE 35.3) y los empaqueta
para el push al backoffice cloud. Best-effort y resiliente: cada fuente va envuelta en
try/except y nunca propaga — un snapshot parcial es mejor que ninguno. El cálculo pesado
vive en el SER9; la nube sólo almacena y muestra.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import requests

CORE_URL = os.environ.get("CORE_URL", "http://localhost:8765")
WINDOW_HOURS = int(os.environ.get("METRICS_WINDOW_HOURS", "24"))
SERIES_BUCKET = int(os.environ.get("METRICS_SERIES_BUCKET", "3600"))


def _get(url: str, timeout: int = 6):
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_metrics_snapshot(hours: int = WINDOW_HOURS) -> dict:
    """Arma el snapshot de métricas. Nunca lanza: campos faltantes quedan vacíos."""
    base = f"{CORE_URL}/metrics"
    q = f"hours={hours}"
    qs = f"{q}&bucket={SERIES_BUCKET}"
    return {
        "schema_version": 1,
        "ts": _now_iso(),
        "window_hours": hours,
        "voice_summary": _get(f"{base}/voice/summary?{q}") or {},
        "voice_series":  _get(f"{base}/voice/series?{qs}") or {},
        "retrains":      (_get(f"{base}/voice/retrains?limit=10") or {}).get("retrains", []),
        "llm_summary":   _get(f"{base}/llm/summary?{q}") or {},
        "llm_by_model":  (_get(f"{base}/llm/by-model?{q}") or {}).get("models", []),
        "llm_by_agent":  (_get(f"{base}/llm/by-agent?{q}") or {}).get("agents", []),
        "llm_series":    _get(f"{base}/llm/series?{qs}") or {},
    }

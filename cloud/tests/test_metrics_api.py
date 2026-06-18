"""Tests de los endpoints de métricas del backoffice cloud (FASE 35.7).

Levanta la app con TestClient, sobreescribe las dependencias de auth (bridge OIDC y
usuario de dashboard) y mockea la capa Firestore — no toca GCP ni valida tokens reales.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import firestore_db as fdb
from app import main, rbac
from app.auth import Principal, require_bridge, require_dashboard_user
from app.models import METRICS_SCHEMA_VERSION

client = TestClient(main.app)


def _principal(role: str) -> Principal:
    return Principal(email=f"{role}@x.z", role=role, caps=rbac.caps_for(role))


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    main.app.dependency_overrides.clear()


SAMPLE = {
    "schema_version": METRICS_SCHEMA_VERSION, "ts": "2026-06-18T00:00:00Z", "window_hours": 24,
    "voice_summary": {"total": 5, "tp": 4, "fp": 1, "fp_rate": 0.2},
    "voice_series": {"labels": [1], "series": []},
    "retrains": [{"version": "v1"}],
    "llm_summary": {"requests": {"requests": 3}, "llm_calls": {"calls": 9}},
    "llm_by_model": [{"model": "qwen2.5:7b", "calls": 9}],
    "llm_by_agent": [{"agent_id": "haos", "steps": 2}],
    "llm_series": {"labels": [1], "series": []},
}


# ── /ingest/metrics (bridge → nube) ────────────────────────────────────────────

def test_ingest_metrics_stores(monkeypatch):
    captured = {}
    monkeypatch.setattr(fdb, "store_metrics", lambda d: captured.update(d))
    main.app.dependency_overrides[require_bridge] = lambda: "bridge-sa@x"
    r = client.post("/ingest/metrics", json=SAMPLE)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert captured["voice_summary"]["total"] == 5
    assert captured["llm_by_model"][0]["model"] == "qwen2.5:7b"


def test_ingest_metrics_bad_schema(monkeypatch):
    monkeypatch.setattr(fdb, "store_metrics", lambda d: None)
    main.app.dependency_overrides[require_bridge] = lambda: "bridge-sa@x"
    bad = {**SAMPLE, "schema_version": 999}
    r = client.post("/ingest/metrics", json=bad)
    assert r.status_code == 422


def test_ingest_metrics_requires_bridge_auth():
    # sin override de auth → falta Authorization Bearer → 401
    r = client.post("/ingest/metrics", json=SAMPLE)
    assert r.status_code == 401


# ── /api/metrics (dashboard → nube, con RBAC) ──────────────────────────────────

def test_api_metrics_admin_sees_detail(monkeypatch):
    monkeypatch.setattr(fdb, "get_metrics", lambda: dict(SAMPLE))
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("admin")
    r = client.get("/api/metrics")
    assert r.status_code == 200
    m = r.json()["metrics"]
    assert m["llm_by_model"] and m["llm_by_agent"] and m["retrains"]


def test_api_metrics_basic_role_filtered(monkeypatch):
    monkeypatch.setattr(fdb, "get_metrics", lambda: dict(SAMPLE))
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("adolescente")
    r = client.get("/api/metrics")
    assert r.status_code == 200
    m = r.json()["metrics"]
    assert m["llm_by_model"] == [] and m["llm_by_agent"] == [] and m["retrains"] == []
    assert m["voice_summary"]["total"] == 5   # resúmenes sí

def test_api_metrics_none_when_empty(monkeypatch):
    monkeypatch.setattr(fdb, "get_metrics", lambda: None)
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("admin")
    r = client.get("/api/metrics")
    assert r.status_code == 200 and r.json() == {"metrics": None}

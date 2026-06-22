"""Tests de los endpoints del dashboard nuevos en FASE 37.6: /api/alerts y /api/logs.

Mismo enfoque que test_metrics_api: TestClient + override de auth + mock de la capa Firestore.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import firestore_db as fdb
from app import main, rbac
from app.auth import Principal, require_dashboard_user

client = TestClient(main.app)


def _principal(role: str) -> Principal:
    return Principal(email=f"{role}@x.z", role=role, caps=rbac.caps_for(role))


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    main.app.dependency_overrides.clear()


# ── /api/alerts (gated por access) ─────────────────────────────────────────────

def test_alerts_from_snapshot(monkeypatch):
    monkeypatch.setattr(fdb, "get_state", lambda: {"alerts": ["doc vence", "lluvia"]})
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("adolescente")
    r = client.get("/api/alerts")
    assert r.status_code == 200 and r.json()["alerts"] == ["doc vence", "lluvia"]


def test_alerts_empty_when_no_state(monkeypatch):
    monkeypatch.setattr(fdb, "get_state", lambda: None)
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("familiar")
    r = client.get("/api/alerts")
    assert r.status_code == 200 and r.json()["alerts"] == []


# ── /api/logs (gated por emit) ─────────────────────────────────────────────────

def test_logs_returns_latest_log_command(monkeypatch):
    cmds = [
        {"type": "service.restart", "status": "done"},
        {"type": "logs.tail", "status": "done", "result": {"ok": True, "output": "linea1\nlinea2"}},
        {"type": "logs.tail", "status": "done", "result": {"ok": True, "output": "vieja"}},
    ]
    monkeypatch.setattr(fdb, "recent_commands", lambda limit=50: cmds)
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("admin")
    r = client.get("/api/logs")
    assert r.status_code == 200
    assert r.json()["log"]["result"]["output"] == "linea1\nlinea2"  # el primero (más reciente)


def test_logs_none_when_no_log_commands(monkeypatch):
    monkeypatch.setattr(fdb, "recent_commands", lambda limit=50: [{"type": "deploy.run"}])
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("admin")
    r = client.get("/api/logs")
    assert r.status_code == 200 and r.json()["log"] is None


def test_logs_requires_emit(monkeypatch):
    monkeypatch.setattr(fdb, "recent_commands", lambda limit=50: [])
    main.app.dependency_overrides[require_dashboard_user] = lambda: _principal("familiar")  # sin emit
    r = client.get("/api/logs")
    assert r.status_code == 403

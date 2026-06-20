"""Tests del bridge: executor (dispatch sin shell) y snapshot (resiliencia)."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import executor  # noqa: E402
import snapshot  # noqa: E402


def test_executor_unknown_type():
    r = executor.execute("nope.bad", {})
    assert not r.ok and "sin handler" in r.error


def test_executor_service_restart_uses_arg_list():
    captured = {}

    class P:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(args, **kw):
        captured["args"] = args
        return P()

    with patch.object(executor.subprocess, "run", fake_run):
        r = executor.execute("service.restart", {"service": "capitan-core"})
    assert r.ok
    # sin shell: lista de args, no string
    assert captured["args"] == ["systemctl", "--user", "restart", "capitan-core"]


def test_executor_logs_tail_builds_command():
    captured = {}

    class P:
        returncode = 0
        stdout = "log"
        stderr = ""

    with patch.object(executor.subprocess, "run", lambda args, **kw: captured.update(args=args) or P()):
        executor.execute("logs.tail", {"service": "capitan-wa", "lines": 50})
    assert captured["args"] == ["journalctl", "--user", "-u", "capitan-wa", "-n", "50", "--no-pager"]


def test_snapshot_resilient_when_all_sources_down():
    # Todas las fuentes caídas: igual devuelve estructura válida (no lanza).
    with patch.object(snapshot, "_get", lambda *a, **k: None), \
         patch.object(snapshot, "_systemctl_active", lambda u: False):
        snap = snapshot.build_snapshot()
    assert snap["schema_version"] == 1
    assert set(snap["services"]) == {"core", "llm", "ear", "backoffice", "wa"}
    assert all(not s["up"] for s in snap["services"].values())
    assert snap["agents"] == [] and snap["users_summary"] == []


def test_snapshot_maps_agents_and_nodes():
    def fake_get(url, timeout=4):
        if url.endswith("/agents"):
            return {"haos": {"status": "active"}, "clima": {"status": "inactive", "proactive": True}}
        if url.endswith("/nodes"):
            return [{"node_id": "comedor", "state": "active", "last_command": "prende la luz",
                     "last_command_ts": 1781581761, "last_latency_ms": 3379, "fp": 2}]
        if url.endswith("/health"):
            return {"status": "ok", "nodes": 1}
        if url.endswith("/users"):
            return {"matias": {"id": "matias", "name": "Matías", "role": "admin"}}
        if url.endswith("/intents"):
            return [{"user_id": "matias", "status": "open"}]
        if url.endswith("/api/tags"):
            return {"models": []}
        return None

    with patch.object(snapshot, "_get", fake_get), \
         patch.object(snapshot, "_systemctl_active", lambda u: True):
        snap = snapshot.build_snapshot()
    assert {a["id"] for a in snap["agents"]} == {"haos", "clima"}
    assert snap["recent_commands"][0]["text"] == "prende la luz"
    assert snap["latency"]["llm_ms"] == 3379
    assert snap["users_summary"][0]["intents_pending"] == 1


# ── metrics_snapshot (FASE 35.5) ────────────────────────────────────────────────

import metrics_snapshot  # noqa: E402


def test_metrics_snapshot_resilient_when_core_down():
    # Core caído: estructura válida, campos vacíos, nunca lanza.
    with patch.object(metrics_snapshot, "_get", lambda *a, **k: None):
        snap = metrics_snapshot.build_metrics_snapshot()
    assert snap["schema_version"] == 1
    assert snap["window_hours"] == 24
    assert snap["voice_summary"] == {} and snap["llm_summary"] == {}
    assert snap["retrains"] == [] and snap["llm_by_model"] == [] and snap["llm_by_agent"] == []


def test_metrics_snapshot_unwraps_list_envelopes():
    # by-model/by-agent/retrains vienen envueltos por la API; el snapshot los desenvuelve.
    def fake_get(url, **k):
        if "by-model" in url: return {"models": [{"model": "qwen2.5:7b", "calls": 3}]}
        if "by-agent" in url: return {"agents": [{"agent_id": "haos", "steps": 2}]}
        if "retrains" in url: return {"retrains": [{"version": "v1"}]}
        if "summary" in url:  return {"total": 5}
        return {"labels": [1, 2], "series": []}
    with patch.object(metrics_snapshot, "_get", fake_get):
        snap = metrics_snapshot.build_metrics_snapshot(hours=6)
    assert snap["window_hours"] == 6
    assert snap["llm_by_model"][0]["model"] == "qwen2.5:7b"
    assert snap["llm_by_agent"][0]["agent_id"] == "haos"
    assert snap["retrains"][0]["version"] == "v1"
    assert snap["voice_series"]["labels"] == [1, 2]


# ── deploy.run / deploy.release invocan el motor único (FASE 34) ───────────────

def test_deploy_run_invokes_engine(monkeypatch):
    import deploy_engine
    captured = {}

    class _Res:
        ok = True
        log = ["línea"]
        def __init__(self): pass

    def _fake(services=None, repo_refs=None, emit=None):
        captured["services"] = services
        captured["repo_refs"] = repo_refs
        if emit:
            emit("motor corrió")
        return type("R", (), {"ok": True})()

    monkeypatch.setattr(deploy_engine, "run_release", _fake)
    r = executor.execute("deploy.run", {})
    assert r.ok
    # default: servicios del motor, sin wa
    assert captured["services"] == list(deploy_engine.DEFAULT_SERVICES)
    assert "motor corrió" in r.output


def test_deploy_run_restart_wa_incluye_wa(monkeypatch):
    import deploy_engine
    captured = {}
    monkeypatch.setattr(deploy_engine, "run_release",
                        lambda services=None, repo_refs=None, emit=None:
                        captured.update(services=services) or type("R", (), {"ok": True})())
    executor.execute("deploy.run", {"restart_wa": True})
    assert "wa" in captured["services"]


def test_deploy_release_passes_refs(monkeypatch):
    import deploy_engine
    captured = {}
    monkeypatch.setattr(deploy_engine, "run_release",
                        lambda services=None, repo_refs=None, emit=None:
                        captured.update(services=services, repo_refs=repo_refs)
                        or type("R", (), {"ok": True})())
    executor.execute("deploy.release",
                     {"services": ["core"], "core_ref": "v1.2", "umbrella_ref": "abc"})
    assert captured["services"] == ["core"]
    assert captured["repo_refs"] == {"core": "v1.2", "umbrella": "abc"}


def test_deploy_release_failure_reports_not_ok(monkeypatch):
    import deploy_engine
    monkeypatch.setattr(deploy_engine, "run_release",
                        lambda services=None, repo_refs=None, emit=None:
                        type("R", (), {"ok": False})())
    r = executor.execute("deploy.release", {})
    assert r.ok is False and "rollback" in r.error

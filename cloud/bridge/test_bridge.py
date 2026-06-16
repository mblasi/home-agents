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

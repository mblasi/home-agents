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


def test_deploy_satellites_marca_nodo(monkeypatch):
    captured = {}

    def fake_post(url, timeout=10):
        captured["url"] = url
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"ok": True, "flagged": ["comedor"]}})()

    monkeypatch.setattr(executor.requests, "post", fake_post)
    r = executor.execute("deploy.satellites", {"node_id": "comedor"})
    assert r.ok is True and "comedor" in r.output
    assert captured["url"].endswith("/nodes/comedor/update")


def test_deploy_satellites_todos_por_default(monkeypatch):
    captured = {}

    def fake_post(url, timeout=10):
        captured["url"] = url
        return type("R", (), {"raise_for_status": lambda self: None,
                              "json": lambda self: {"ok": True, "flagged": ["comedor", "pieza"]}})()

    monkeypatch.setattr(executor.requests, "post", fake_post)
    executor.execute("deploy.satellites", {})
    assert captured["url"].endswith("/nodes/*/update")   # sin node_id → todos


# ── Logs en vivo (D5): emit del executor + batching del bridge ─────────────────

def test_execute_passes_emit_to_deploy(monkeypatch):
    import deploy_engine

    def _fake(services=None, repo_refs=None, emit=None):
        if emit:
            emit("línea del motor")
        return type("R", (), {"ok": True})()

    monkeypatch.setattr(deploy_engine, "run_release", _fake)
    got = []
    r = executor.execute("deploy.run", {}, emit=got.append)
    assert r.ok and "línea del motor" in got


def test_execute_ignores_emit_for_non_streaming(monkeypatch):
    # service.restart no es streaming → execute no le pasa emit y no rompe.
    class P:
        returncode = 0
        stdout = "ok"
        stderr = ""
    monkeypatch.setattr(executor.subprocess, "run", lambda *a, **k: P())
    r = executor.execute("service.restart", {"service": "capitan-core"}, emit=lambda l: None)
    assert r.ok


def test_progress_emitter_batches_and_flushes(monkeypatch):
    # Importa cloud_bridge con los módulos google mockeados (no están en el venv de test) y las
    # env vars que lee a nivel módulo.
    import os
    import sys
    from unittest.mock import MagicMock
    for m in ("google", "google.auth", "google.auth.transport",
              "google.auth.transport.requests", "google.oauth2", "google.oauth2.service_account"):
        sys.modules.setdefault(m, MagicMock())
    os.environ.setdefault("CLOUD_URL", "https://cloud.test")
    os.environ.setdefault("BRIDGE_SA_KEY", "{}")
    import cloud_bridge

    posts = []

    class _Sess:
        def post(self, url, json=None, timeout=None):
            posts.append((url, json))
            return type("R", (), {"raise_for_status": lambda self: None})()

    monkeypatch.setattr(cloud_bridge, "PROGRESS_BATCH", 2)
    emit = cloud_bridge._progress_emitter(_Sess(), "cmd1")
    emit("a")
    assert posts == []                      # batch incompleto, sin POST
    emit("b")
    assert len(posts) == 1                  # flush al llenar el lote
    assert posts[0][0].endswith("/commands/cmd1/progress")
    assert posts[0][1] == {"lines": ["a", "b"]}
    emit("c")
    emit.flush()
    assert posts[1][1] == {"lines": ["c"]}  # flush manual vacía el resto


# ── Matriz de versiones en el snapshot (FASE 34 T5) ───────────────────────────

def test_snapshot_versions_panels_y_ser9():
    def fake_get(url, timeout=4):
        if url.endswith("/satellite/version"):
            return {"version": "abc123def456789xyz"}
        if url.endswith("/nodes"):
            return [{"node_id": "comedor", "state": "active", "version": "abc123def456"},
                    {"node_id": "pieza", "state": "active", "version": "vieja000"}]
        if url.endswith("/health"):
            return {"status": "ok", "nodes": 2}
        return None
    with patch.object(snapshot, "_get", fake_get), \
         patch.object(snapshot, "_systemctl_active", lambda u: True), \
         patch.object(snapshot, "_maybe_fetch", lambda *a, **k: None):  # sin git fetch real
        snap = snapshot.build_snapshot()
    v = snap["versions"]
    assert isinstance(v["targets"], list)               # matriz unificada de targets (34.15)
    assert v["satellite_expected"] == "abc123def456"    # [:12]
    byid = {t["id"]: t for t in v["targets"]}
    # los paneles son targets dinámicos (id "panel:<node_id>"), kind satellite
    assert byid["panel:comedor"]["kind"] == "satellite"
    assert byid["panel:comedor"]["behind"] is False     # version == expected[:12]
    assert byid["panel:pieza"]["behind"] is True        # rezagado
    assert byid["panel:comedor"]["command"] == "deploy.satellites"
    # los services del SER9 también son targets (al menos core/backoffice)
    assert any(t["id"] == "core" and t["kind"] == "service" for t in v["targets"])

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


# ── FASE 37.7: campos nuevos del snapshot (alerts, counts, wakeword.status) ──────

def test_snapshot_emits_new_fields_and_validates():
    from app.models import StateSnapshot

    def fake_get(url, timeout=4):
        if url.endswith("/alerts/recent"):       return ["doc vence", "lluvia fuerte"]
        if url.endswith("/wakeword/train/status"): return {"status": "running"}
        if url.endswith("/intents"):              return [{"user_id": "m"}, {"user_id": "j"}]
        if url.endswith("/goals"):                return [{"id": "g1"}]
        if url.endswith("/routines"):             return [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]
        if url.endswith("/conversations"):        return [{"id": "c1"}]
        return None

    with patch.object(snapshot, "_get", fake_get), \
         patch.object(snapshot, "_systemctl_active", lambda u: False):
        snap = snapshot.build_snapshot()
    assert snap["alerts"] == ["doc vence", "lluvia fuerte"]
    assert snap["wakeword"]["status"] == "running"
    assert snap["counts"] == {"intents": 2, "goals": 1, "routines": 3, "conversations": 1}
    # No usa el endpoint destructivo /alerts (drain): sólo /alerts/recent (peek).
    StateSnapshot(**snap)   # el shape del bridge valida contra el contrato de la nube


def test_snapshot_new_fields_default_when_down():
    with patch.object(snapshot, "_get", lambda *a, **k: None), \
         patch.object(snapshot, "_systemctl_active", lambda u: False):
        snap = snapshot.build_snapshot()
    assert snap["alerts"] == []
    assert snap["counts"] == {"intents": 0, "goals": 0, "routines": 0, "conversations": 0}
    assert snap["wakeword"]["status"] == "idle"


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


# ── FASE 37.8: handlers de operación (agent.toggle / panel.reboot / proactive.run) ──

def _resp(payload=None):
    return type("R", (), {"raise_for_status": lambda self: None,
                          "json": lambda self: payload or {}})()


def test_agent_toggle_patches_core_status(monkeypatch):
    captured = {}

    def fake_patch(url, json=None, timeout=10):
        captured.update(url=url, json=json)
        return _resp()

    monkeypatch.setattr(executor.requests, "patch", fake_patch)
    r = executor.execute("agent.toggle", {"agent_id": "haos", "status": "planned"})
    assert r.ok and captured["url"].endswith("/agents/haos/status")
    assert captured["json"] == {"status": "planned"}


def test_proactive_run_posts_core(monkeypatch):
    captured = {}

    def fake_post(url, timeout=60):
        captured["url"] = url
        return _resp({"ran": True})

    monkeypatch.setattr(executor.requests, "post", fake_post)
    r = executor.execute("proactive.run", {"agent_id": "clima"})
    assert r.ok and captured["url"].endswith("/proactive/clima/run")


def test_panel_reboot_resolves_ip_and_runs_script(monkeypatch):
    captured = {}
    monkeypatch.setattr(executor.requests, "get",
        lambda url, timeout=8: _resp([{"node_id": "comedor", "ip": "192.168.68.113"}]))

    class P:
        returncode = 0; stdout = "Reiniciando"; stderr = ""

    def fake_run(args, **kw):
        captured.update(args=args, ip=kw.get("env", {}).get("NSPANEL_IP"))
        return P()

    monkeypatch.setattr(executor.subprocess, "run", fake_run)
    r = executor.execute("panel.reboot", {"node_id": "comedor"})
    assert r.ok
    assert captured["args"][0] == "bash" and captured["args"][-1] == "reboot"
    assert captured["ip"] == "192.168.68.113"   # IP resuelta del registro → env del script


def test_panel_reboot_unknown_node(monkeypatch):
    monkeypatch.setattr(executor.requests, "get", lambda url, timeout=8: _resp([]))
    r = executor.execute("panel.reboot", {"node_id": "fantasma"})
    assert not r.ok and "IP" in r.error


def test_logs_satellite_calls_audio_server(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=20):
        captured.update(url=url, params=params)
        return type("R", (), {"status_code": 200, "json": lambda self: {"log": "linea1\nlinea2"}})()

    monkeypatch.setattr(executor.requests, "get", fake_get)
    r = executor.execute("logs.satellite", {"node_id": "comedor", "lines": 50})
    assert r.ok and r.output == "linea1\nlinea2"
    assert captured["url"].endswith("/nodes/comedor/satellite-log")
    assert captured["params"] == {"lines": 50}


def test_logs_satellite_propagates_error(monkeypatch):
    def fake_get(url, params=None, timeout=20):
        return type("R", (), {"status_code": 404, "headers": {"content-type": "application/json"},
                              "json": lambda self: {"detail": "panel sin IP"}})()

    monkeypatch.setattr(executor.requests, "get", fake_get)
    r = executor.execute("logs.satellite", {"node_id": "fantasma"})
    assert not r.ok and "404" in r.error


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
    # los services del Brain también son targets (al menos core/backoffice)
    assert any(t["id"] == "core" and t["kind"] == "service" for t in v["targets"])


# ── FASE 38: panel.config (executor + snapshot) ───────────────────────────────

def test_executor_panel_config_upserts_core_and_flags_audio():
    posts = []

    class R:
        def __init__(self, data=None):
            self._d = data or {}
        def raise_for_status(self): pass
        def json(self): return self._d

    def fake_get(url, timeout=8):
        assert url.endswith("/panels")
        return R([{"name": "comedor", "node_id": "nspanel-comedor"}])

    def fake_post(url, json=None, timeout=10):
        posts.append((url, json))
        return R({"ok": True})

    with patch.object(executor.requests, "get", fake_get), \
         patch.object(executor.requests, "post", fake_post):
        r = executor.execute("panel.config", {"node_id": "nspanel-comedor",
                                              "screen_timeout_secs": 90})
    assert r.ok
    core_post = next(p for p in posts if p[0].endswith("/panels"))
    assert core_post[1] == {"name": "comedor", "config": {"screen_timeout_secs": 90}}
    assert any(u.endswith("/nodes/nspanel-comedor/config-changed") for u, _ in posts)


def test_executor_panel_config_name_fallback_from_node_id():
    posts = []

    class R:
        def raise_for_status(self): pass
        def json(self): return []   # panel no registrado

    def fake_post(url, json=None, timeout=10):
        posts.append((url, json))
        return R()

    with patch.object(executor.requests, "get", lambda *a, **k: R()), \
         patch.object(executor.requests, "post", fake_post):
        r = executor.execute("panel.config", {"node_id": "nspanel-cocina",
                                              "default_dashboard": "http://h/x/0"})
    assert r.ok
    core_post = next(p for p in posts if p[0].endswith("/panels"))
    assert core_post[1]["name"] == "cocina"   # nspanel- stripped


def test_executor_panel_config_no_params_rejected():
    r = executor.execute("panel.config", {"node_id": "nspanel-comedor"})
    assert not r.ok and "nada para configurar" in r.error


def test_snapshot_nodes_carry_config_and_dashboards():
    from app.models import StateSnapshot

    dashboards = [{"title": "Comedor", "url_path": "lovelace-comedor",
                   "url": "http://h/lovelace-comedor/0"}]

    def fake_get(url, timeout=4):
        if url.endswith("/nodes"):
            return [{"node_id": "nspanel-comedor", "state": "active"}]
        if url.endswith("/panels"):
            return [{"name": "comedor", "node_id": "nspanel-comedor",
                     "config": {"screen_timeout_secs": 120}}]
        if url.endswith("/dashboards"):
            return dashboards
        return None

    with patch.object(snapshot, "_get", fake_get), \
         patch.object(snapshot, "_systemctl_active", lambda u: False):
        snap = snapshot.build_snapshot()
    node = snap["wakeword"]["nodes"][0]
    assert node["config"] == {"screen_timeout_secs": 120}
    assert snap["dashboards"] == dashboards
    StateSnapshot(**snap)   # valida contra el contrato de la nube


def test_snapshot_nodes_carry_device_config():
    from app.models import StateSnapshot

    def fake_get(url, timeout=4):
        if url.endswith("/nodes"):
            return [{"node_id": "nspanel-comedor", "state": "active",
                     "device_config": {"screen_timeout_secs": 120}}]
        if url.endswith("/panels"):
            return [{"name": "comedor", "node_id": "nspanel-comedor", "config": {}}]
        if url.endswith("/dashboards"):
            return []
        return None

    with patch.object(snapshot, "_get", fake_get), \
         patch.object(snapshot, "_systemctl_active", lambda u: False):
        snap = snapshot.build_snapshot()
    node = snap["wakeword"]["nodes"][0]
    assert node["device_config"] == {"screen_timeout_secs": 120}
    StateSnapshot(**snap)

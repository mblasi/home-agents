"""Issue #766 — la página Plan se arma desde los issues de GitHub (labels `fase-N`).

Sin red real: `requests.get` se parchea. Correr con:
    cd backoffice && python -m pytest tests/ -q
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import plan_gh


def _issue(number, title, state="open", labels=(), pr=False):
    d = {
        "number": number,
        "title": title,
        "state": state,
        "html_url": f"https://github.com/mblasi/home-agents/issues/{number}",
        "labels": [{"name": n, "description": desc} for n, desc in labels],
    }
    if pr:
        d["pull_request"] = {}
    return d


F39 = ("fase-39", "Mensajería P2P entre usuarios")
F2 = ("fase-2", "Agente domótica completo")
F35 = ("fase-3.5", "Integración WhatsApp")
WIP = ("status:wip", "Work in progress")


@pytest.fixture(autouse=True)
def _reset_cache():
    plan_gh.clear_cache()
    yield
    plan_gh.clear_cache()


# ── parse_title ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("title,tid,text", [
    ("[39.1] Modelo de sesión P2P", "39.1", "Modelo de sesión P2P"),
    ("34.17 — Compartimentación física", "34.17", "Compartimentación física"),
    ("6.21 Milestones en histograma", "6.21", "Milestones en histograma"),
    ("Backoffice local: el nombre queda", "", "Backoffice local: el nombre queda"),
    ("[8.32] Investigar por qué", "8.32", "Investigar por qué"),
])
def test_parse_title(title, tid, text):
    assert plan_gh.parse_title(title) == (tid, text)


# ── build_phases ───────────────────────────────────────────────────────────────

def test_groups_by_fase_label_and_sorts_naturally():
    issues = [
        _issue(1, "[39.1] a", labels=[F39]),
        _issue(2, "[2.1] b", "closed", labels=[F2]),
        _issue(3, "[3.5.1] c", "closed", labels=[F35]),
    ]
    phases = plan_gh.build_phases(issues)
    assert [p["id"] for p in phases] == ["2", "3.5", "39"]
    assert phases[0]["title"] == "Agente domótica completo"


def test_phase_state_and_progress():
    issues = [
        _issue(1, "[2.1] a", "closed", labels=[F2]),
        _issue(2, "[2.2] b", "closed", labels=[F2]),
        _issue(3, "[39.1] c", "closed", labels=[F39]),
        _issue(4, "[39.2] d", labels=[F39]),
        _issue(5, "[3.5.1] e", labels=[F35]),
    ]
    by_id = {p["id"]: p for p in plan_gh.build_phases(issues)}
    assert by_id["2"]["estado"] == "COMPLETA" and by_id["2"]["pct"] == 100
    assert by_id["39"]["estado"] == "EN CURSO"
    assert (by_id["39"]["tasks_done"], by_id["39"]["tasks_total"], by_id["39"]["pct"]) == (1, 2, 50)
    assert by_id["3.5"]["estado"] == "Pendiente" and by_id["3.5"]["pct"] == 0


def test_wip_label_marks_phase_en_curso():
    phases = plan_gh.build_phases([_issue(1, "[39.1] a", labels=[F39, WIP])])
    assert phases[0]["estado"] == "EN CURSO"


def test_task_fields_and_link():
    phases = plan_gh.build_phases([_issue(657, "[39.1] Modelo de sesión", labels=[F39])])
    t = phases[0]["tasks"][0]
    assert t == {
        "id": "39.1", "text": "Modelo de sesión", "done": False, "gh_num": 657,
        "gh_url": "https://github.com/mblasi/home-agents/issues/657",
    }


def test_tasks_sorted_by_task_id_then_number():
    issues = [
        _issue(10, "[39.10] z", labels=[F39]),
        _issue(11, "[39.2] y", labels=[F39]),
        _issue(12, "sin id", labels=[F39]),
    ]
    ids = [t["id"] for t in plan_gh.build_phases(issues)[0]["tasks"]]
    assert ids == ["39.2", "39.10", ""]


def test_pull_requests_are_ignored():
    phases = plan_gh.build_phases([_issue(1, "[39.1] pr", labels=[F39], pr=True)])
    assert phases == []


def test_open_issues_without_fase_go_to_sin_fase():
    issues = [
        _issue(1, "Bug suelto"),
        _issue(2, "Cerrado sin fase", "closed"),
    ]
    phases = plan_gh.build_phases(issues)
    assert len(phases) == 1 and phases[0]["id"] == plan_gh.NO_PHASE_ID
    assert [t["gh_num"] for t in phases[0]["tasks"]] == [1]
    assert phases[0]["estado"] == "Pendiente"


def test_sin_fase_goes_last():
    issues = [_issue(1, "suelto"), _issue(2, "[39.1] a", labels=[F39])]
    assert [p["id"] for p in plan_gh.build_phases(issues)] == ["39", plan_gh.NO_PHASE_ID]


def test_phase_without_description_falls_back_to_id():
    phases = plan_gh.build_phases([_issue(1, "[7.1] a", labels=[("fase-7", None)])])
    assert phases[0]["title"] == "FASE 7"


# ── fetch + caché ──────────────────────────────────────────────────────────────

def _resp(items, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = items
    r.raise_for_status.side_effect = None if status < 400 else RuntimeError(f"HTTP {status}")
    return r


def test_fetch_paginates_until_short_page(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    monkeypatch.setattr(plan_gh, "PAGE_SIZE", 2)
    f1 = [("fase-1", "x")]
    pages = [
        _resp([_issue(1, "[1.1] a", labels=f1), _issue(2, "[1.2] b", labels=f1)]),
        _resp([_issue(3, "[1.3] c", labels=f1)]),
    ]
    with patch.object(plan_gh.requests, "get", side_effect=pages) as g:
        data = plan_gh.get_plan()
    assert g.call_count == 2
    assert data["phases"][0]["tasks_total"] == 3
    assert data["error"] is None


def test_fetch_queries_every_configured_repo(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/a", "o/b"])
    with patch.object(plan_gh.requests, "get", return_value=_resp([])) as g:
        plan_gh.get_plan()
    urls = [c.args[0] for c in g.call_args_list]
    assert any("/repos/o/a/issues" in u for u in urls)
    assert any("/repos/o/b/issues" in u for u in urls)


def test_token_header_only_when_configured(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    with patch.object(plan_gh.requests, "get", return_value=_resp([])) as g:
        plan_gh.get_plan()
    assert g.call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
    plan_gh.clear_cache()
    monkeypatch.delenv("GITHUB_TOKEN")
    with patch.object(plan_gh.requests, "get", return_value=_resp([])) as g:
        plan_gh.get_plan()
    assert "Authorization" not in g.call_args.kwargs["headers"]


def test_cache_within_ttl_avoids_refetch(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    with patch.object(plan_gh.requests, "get", return_value=_resp([])) as g:
        plan_gh.get_plan()
        plan_gh.get_plan()
    assert g.call_count == 1


def test_refetch_after_ttl(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    now = [1000.0]
    monkeypatch.setattr(plan_gh.time, "time", lambda: now[0])
    with patch.object(plan_gh.requests, "get", return_value=_resp([])) as g:
        plan_gh.get_plan()
        now[0] += plan_gh.CACHE_TTL + 1
        plan_gh.get_plan()
    assert g.call_count == 2


def test_stale_cache_served_when_github_fails(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    now = [1000.0]
    monkeypatch.setattr(plan_gh.time, "time", lambda: now[0])
    ok = _resp([_issue(1, "[39.1] a", labels=[F39])])
    with patch.object(plan_gh.requests, "get", return_value=ok):
        plan_gh.get_plan()
    now[0] += plan_gh.CACHE_TTL + 1
    with patch.object(plan_gh.requests, "get", side_effect=OSError("down")):
        data = plan_gh.get_plan()
    assert data["phases"][0]["tasks_total"] == 1
    assert data["stale"] is True and "down" in data["error"]


def test_no_cache_and_github_down_returns_empty_with_error(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    with patch.object(plan_gh.requests, "get", side_effect=OSError("down")):
        data = plan_gh.get_plan()
    assert data["phases"] == [] and "down" in data["error"]


def test_failed_refresh_does_not_hammer_github(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    with patch.object(plan_gh.requests, "get", side_effect=OSError("down")) as g:
        plan_gh.get_plan()
        plan_gh.get_plan()
    assert g.call_count == 1


# ── server: ya no depende de estado.md / issues.yaml ───────────────────────────

def test_server_no_longer_reads_masterplan_files():
    import server
    src = Path(server.__file__).read_text()
    assert "estado.md" not in src and "issues.yaml" not in src
    assert not hasattr(server, "_parse_plan") and not hasattr(server, "_load_issue_urls")


# ── ruta /plan ─────────────────────────────────────────────────────────────────

def _client():
    from fastapi.testclient import TestClient
    import server
    return TestClient(server.app)


def test_plan_page_renders_from_github(monkeypatch):
    issues = [
        _issue(657, "[39.1] Modelo de sesión P2P", "closed", labels=[F39]),
        _issue(658, "[39.2] Agente messenger", labels=[F39]),
    ]
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    with patch.object(plan_gh.requests, "get", return_value=_resp(issues)):
        r = _client().get("/plan")
    assert r.status_code == 200
    assert "Mensajería P2P entre usuarios" in r.text
    assert "Modelo de sesión P2P" in r.text and "#657" in r.text
    assert "masterplan/estado.md" not in r.text


def test_plan_page_shows_notice_when_github_down(monkeypatch):
    monkeypatch.setattr(plan_gh, "REPOS", ["o/r"])
    with patch.object(plan_gh.requests, "get", side_effect=OSError("sin red")):
        r = _client().get("/plan")
    assert r.status_code == 200
    assert "No se pudo leer el plan desde GitHub" in r.text and "sin red" in r.text

"""Tests del RBAC del backoffice en la nube (33.21)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import rbac


def test_admin_full():
    c = rbac.caps_for("admin")
    assert c == {"access": True, "view_full": True, "view_pii": True, "emit": True}


def test_familiar_readonly():
    c = rbac.caps_for("familiar")
    assert c["access"] and c["view_full"] and not c["emit"]


def test_adolescente_basic_readonly():
    c = rbac.caps_for("adolescente")
    assert c["access"] and not c["view_full"] and not c["emit"]


def test_nino_invitado_guest_no_access():
    for role in ("niño", "invitado", "guest", "", None, "loquesea"):
        assert rbac.caps_for(role)["access"] is False


# ── FASE 37.2: view_pii admin-only, estrictamente más restrictiva que view_full ──

def test_view_pii_admin_only():
    assert rbac.caps_for("admin")["view_pii"] is True
    assert rbac.caps_for("familiar")["view_pii"] is False
    assert rbac.caps_for("adolescente")["view_pii"] is False
    assert rbac.caps_for(None)["view_pii"] is False


def test_filter_state_redacts_command_text_without_view_pii():
    state = {"recent_commands": [{"ts": "t", "text": "prendé la luz del cuarto",
                                  "agent": "comedor", "ok": True, "latency_ms": 12}],
             "counts": {"conversations": 5}}
    out = rbac.filter_state(state, rbac.caps_for("familiar"))   # view_full sí, view_pii no
    assert out["recent_commands"][0]["text"] == ""              # contenido redactado
    assert out["recent_commands"][0]["agent"] == "comedor"      # metadata conservada
    assert out["recent_commands"][0]["latency_ms"] == 12
    assert out["counts"] == {"conversations": 5}                # conteos siempre quedan


def test_filter_state_keeps_command_text_for_admin():
    state = {"recent_commands": [{"ts": "t", "text": "prendé la luz", "agent": "x", "ok": True}]}
    out = rbac.filter_state(state, rbac.caps_for("admin"))
    assert out["recent_commands"][0]["text"] == "prendé la luz"


def test_filter_state_redacts_users_for_basic():
    state = {"services": {}, "users_summary": [{"id": "matias", "email": "x@y.z"}]}
    out = rbac.filter_state(state, rbac.caps_for("adolescente"))
    assert out["users_summary"] == []
    assert "services" in out


def test_filter_state_keeps_users_for_full():
    state = {"users_summary": [{"id": "matias"}]}
    out = rbac.filter_state(state, rbac.caps_for("familiar"))
    assert out["users_summary"] == [{"id": "matias"}]

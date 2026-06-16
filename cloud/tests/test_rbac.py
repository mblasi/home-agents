"""Tests del RBAC del backoffice en la nube (33.21)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import rbac


def test_admin_full():
    c = rbac.caps_for("admin")
    assert c == {"access": True, "view_full": True, "emit": True}


def test_familiar_readonly():
    c = rbac.caps_for("familiar")
    assert c["access"] and c["view_full"] and not c["emit"]


def test_adolescente_basic_readonly():
    c = rbac.caps_for("adolescente")
    assert c["access"] and not c["view_full"] and not c["emit"]


def test_nino_invitado_guest_no_access():
    for role in ("niño", "invitado", "guest", "", None, "loquesea"):
        assert rbac.caps_for(role)["access"] is False


def test_filter_state_redacts_users_for_basic():
    state = {"services": {}, "users_summary": [{"id": "matias", "email": "x@y.z"}]}
    out = rbac.filter_state(state, rbac.caps_for("adolescente"))
    assert out["users_summary"] == []
    assert "services" in out


def test_filter_state_keeps_users_for_full():
    state = {"users_summary": [{"id": "matias"}]}
    out = rbac.filter_state(state, rbac.caps_for("familiar"))
    assert out["users_summary"] == [{"id": "matias"}]

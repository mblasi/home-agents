"""Tests de require_dashboard_user contra el roster (33.20)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import auth
from fastapi import HTTPException


@pytest.fixture
def fake_token(monkeypatch):
    """Hace que verify_firebase_token devuelva claims fijos por email."""
    def _set(email, verified=True):
        monkeypatch.setattr(
            auth.ga_id_token, "verify_firebase_token",
            lambda *a, **k: {"email": email, "email_verified": verified},
        )
    return _set


def _roster(monkeypatch, mapping):
    monkeypatch.setattr(auth.fdb, "get_roster", lambda: mapping)


def test_admin_from_roster(fake_token, monkeypatch):
    fake_token("matias@blasi.ar")
    _roster(monkeypatch, {"matias@blasi.ar": "admin"})
    p = auth.require_dashboard_user("Bearer x")
    assert p.role == "admin" and p.caps["emit"]


def test_familiar_readonly_from_roster(fake_token, monkeypatch):
    fake_token("pareja@gmail.com")
    _roster(monkeypatch, {"pareja@gmail.com": "familiar"})
    p = auth.require_dashboard_user("Bearer x")
    assert p.role == "familiar" and p.caps["view_full"] and not p.caps["emit"]


def test_unknown_email_rejected(fake_token, monkeypatch):
    fake_token("intruso@x.com")
    _roster(monkeypatch, {"matias@blasi.ar": "admin"})
    monkeypatch.setattr(auth, "ALLOWED_EMAILS", set())
    with pytest.raises(HTTPException) as exc:
        auth.require_dashboard_user("Bearer x")
    assert exc.value.status_code == 403


def test_role_without_access_rejected(fake_token, monkeypatch):
    fake_token("nino@x.com")
    _roster(monkeypatch, {"nino@x.com": "niño"})
    monkeypatch.setattr(auth, "ALLOWED_EMAILS", set())
    with pytest.raises(HTTPException) as exc:
        auth.require_dashboard_user("Bearer x")
    assert exc.value.status_code == 403


def test_bootstrap_allowed_emails(fake_token, monkeypatch):
    fake_token("boss@blasi.ar")
    _roster(monkeypatch, {})  # roster vacío
    monkeypatch.setattr(auth, "ALLOWED_EMAILS", {"boss@blasi.ar"})
    p = auth.require_dashboard_user("Bearer x")
    assert p.role == "admin"


def test_unverified_email_401(fake_token, monkeypatch):
    fake_token("matias@blasi.ar", verified=False)
    _roster(monkeypatch, {"matias@blasi.ar": "admin"})
    with pytest.raises(HTTPException) as exc:
        auth.require_dashboard_user("Bearer x")
    assert exc.value.status_code == 401

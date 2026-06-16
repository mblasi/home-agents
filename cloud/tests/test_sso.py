"""Tests del token SSO firmado (33.22)."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import sso


def _secret(monkeypatch, val=b"supersecreto-de-prueba"):
    monkeypatch.setattr(sso, "SSO_SECRET", val)


def test_mint_verify_roundtrip(monkeypatch):
    _secret(monkeypatch)
    tok = sso.mint("matias@blasi.ar", "admin")
    p = sso.verify(tok)
    assert p["email"] == "matias@blasi.ar" and p["role"] == "admin"


def test_tampered_token_rejected(monkeypatch):
    _secret(monkeypatch)
    tok = sso.mint("matias@blasi.ar", "admin")
    body, sig = tok.split(".", 1)
    forged = body + "." + ("A" * len(sig))
    assert sso.verify(forged) is None


def test_expired_rejected(monkeypatch):
    _secret(monkeypatch)
    tok = sso.mint("x@y.z", "familiar", ttl=-1)
    assert sso.verify(tok) is None


def test_wrong_secret_rejected(monkeypatch):
    _secret(monkeypatch, b"secreto-A")
    tok = sso.mint("x@y.z", "admin")
    _secret(monkeypatch, b"secreto-B")
    assert sso.verify(tok) is None


def test_no_secret_returns_none(monkeypatch):
    _secret(monkeypatch, b"")
    assert sso.verify("a.b") is None


def test_role_escalation_via_tamper_blocked(monkeypatch):
    # Cambiar el rol en el payload invalida la firma.
    _secret(monkeypatch)
    tok = sso.mint("x@y.z", "adolescente")
    import base64, json
    body, sig = tok.split(".", 1)
    payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    payload["role"] = "admin"
    forged_body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    assert sso.verify(f"{forged_body}.{sig}") is None

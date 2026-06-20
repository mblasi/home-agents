"""Tests del motor de deploy (FASE 34): orquestación snapshot→deploy→health→rollback con
git/systemd/http mockeados. No toca el repo real, ni systemctl, ni la red."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

import deploy_engine as de  # noqa: E402


@pytest.fixture
def state_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(de, "STATE_PATH", str(tmp_path / "deploy_state.json"))
    monkeypatch.setattr(de, "HEALTH_RETRIES", 2)
    monkeypatch.setattr(de, "HEALTH_BACKOFF", 0.0)
    return tmp_path


class _FakeGit:
    """Simula `git rev-parse --short HEAD` con un sha que cambia tras un checkout, y registra
    los comandos corridos. Cualquier otro git/pip/systemctl devuelve ok salvo los marcados fail."""
    def __init__(self, head="aaaaaaa", fail=()):
        self.head = head
        self.fail = set(fail)        # substrings de comando que deben fallar
        self.calls: list[list[str]] = []

    def __call__(self, args, emit, *, timeout=300, cwd=None):
        self.calls.append(args)
        joined = " ".join(args)
        for f in self.fail:
            if f in joined:
                return de.RunResult(False, f"forced-fail: {f}")
        if "rev-parse" in args:
            return de.RunResult(True, self.head)
        if "checkout" in args:
            self.head = args[-1].replace("origin/", "")[:7] or self.head  # nuevo sha
        return de.RunResult(True, "ok")


def _setup(monkeypatch, fake):
    monkeypatch.setattr(de, "_run", fake)


# ── happy path ────────────────────────────────────────────────────────────────

def test_release_ok_deploys_and_records_version(state_tmp, monkeypatch):
    fake = _FakeGit(head="old1234")
    _setup(monkeypatch, fake)
    monkeypatch.setattr(de, "_http_ok", lambda url, timeout=5.0: True)

    res = de.run_release(["core"], {"core": "abc1234"})
    assert res.ok
    assert res.components["core"]["ok"] is True
    assert res.components["core"]["rolled_back"] is False
    # snapshot capturó el sha viejo antes del checkout
    assert res.components["core"]["snapshot"] == "old1234"
    # restart de la unit ocurrió
    assert any("restart" in c and "capitan-core" in c for c in fake.calls)
    # versión registrada en el estado persistido
    state = de.load_state()
    assert state["components"]["core"]["status"] == "deployed"
    assert state["last_release"]["ok"] is True


def test_release_default_ref_is_origin_main(state_tmp, monkeypatch):
    fake = _FakeGit()
    _setup(monkeypatch, fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    de.run_release(["wa"])   # wa no tiene health_url ni requirements
    assert any(c[:3] == ["git", "-C", os.path.join(de.REPO_DIR, "")] or "checkout" in c
               and c[-1] == "origin/main" for c in fake.calls)


# ── health falla → rollback ─────────────────────────────────────────────────────

def test_release_health_fail_triggers_rollback(state_tmp, monkeypatch):
    fake = _FakeGit(head="good999")
    _setup(monkeypatch, fake)
    # health HTTP siempre falla → tras el deploy se gatilla rollback; is-active (systemctl) ok
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: False)

    res = de.run_release(["core"], {"core": "bad5678"})
    assert res.ok is False
    assert res.components["core"]["ok"] is False
    assert res.components["core"]["rolled_back"] is True
    # rollback hizo checkout del sha del snapshot (good999)
    checkouts = [c[-1] for c in fake.calls if "checkout" in c]
    assert "good999" in checkouts
    state = de.load_state()
    assert state["components"]["core"]["status"] in ("rolled_back", "broken")


def test_release_deploy_fail_triggers_rollback(state_tmp, monkeypatch):
    # el checkout del ref pedido falla → deploy False → rollback
    fake = _FakeGit(head="snap111", fail=("checkout --quiet bad",))
    _setup(monkeypatch, fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)

    res = de.run_release(["core"], {"core": "bad"})
    assert res.ok is False
    assert res.components["core"]["rolled_back"] is True


def test_release_requirements_install_only_when_version_changed(state_tmp, monkeypatch):
    # HEAD no cambia (checkout al mismo sha) → no se reinstala requirements
    fake = _FakeGit(head="same777")
    monkeypatch.setattr(fake, "head", "same777")
    # forzar que el checkout NO cambie el head
    orig = fake.__call__

    def _call(args, emit, **kw):
        if "checkout" in args:
            fake.calls.append(args)
            return de.RunResult(True, "ok")   # no muta head
        return orig(args, emit, **kw)

    monkeypatch.setattr(de, "_run", _call)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    de.run_release(["core"], {"core": "same777"})
    assert not any("install" in c for c in fake.calls)


# ── targets / parsing ───────────────────────────────────────────────────────────

def test_unknown_target_raises():
    with pytest.raises(ValueError):
        de.get_target("nope")


def test_parse_refs():
    assert de._parse_refs(["core=abc", "ear=v1.2"]) == {"core": "abc", "ear": "v1.2"}


def test_parse_refs_invalid():
    with pytest.raises(SystemExit):
        de._parse_refs(["coreabc"])


def test_emit_callback_receives_lines(state_tmp, monkeypatch):
    fake = _FakeGit()
    _setup(monkeypatch, fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    lines: list[str] = []
    res = de.run_release(["wa"], emit=lines.append)
    assert lines == res.log and len(lines) > 0
    assert any("deploy wa" in l for l in lines)


def test_multiple_targets_independent(state_tmp, monkeypatch):
    fake = _FakeGit()
    _setup(monkeypatch, fake)
    # core sano, ear con health roto
    monkeypatch.setattr(de, "_http_ok",
                        lambda url, timeout=5.0: "8765" in url)
    res = de.run_release(["core", "ear"])
    assert res.components["core"]["ok"] is True
    assert res.components["ear"]["ok"] is False
    assert res.ok is False

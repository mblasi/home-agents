"""Tests del motor de deploy (FASE 34): modelo repo+service, orquestación snapshot→pin→install
→restart→health→rollback con git/systemd/http mockeados. No toca el repo real ni la red."""
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


class _Fake:
    """Mock de `_run`: trackea el HEAD por git dir (cambia con checkout), y deja pasar fetch/
    pip/systemctl salvo los marcados en `fail` (substrings del comando)."""
    def __init__(self, heads=None, fail=()):
        self.heads = dict(heads or {})
        self.fail = set(fail)
        self.calls: list[list[str]] = []

    def __call__(self, args, emit, *, timeout=300):
        self.calls.append(args)
        joined = " ".join(args)
        for f in self.fail:
            if f in joined:
                return de.RunResult(False, f"fail:{f}")
        if args[0] == "git" and "-C" in args:
            gd = args[args.index("-C") + 1]
            if "rev-parse" in args:
                return de.RunResult(True, self.heads.get(gd, "init000"))
            if "checkout" in args:
                self.heads[gd] = (args[-1].replace("origin/", "")[:7]) or self.heads.get(gd, "")
        return de.RunResult(True, "ok")

    def did(self, *substrs) -> bool:
        return any(all(x in " ".join(c) for x in substrs) for c in self.calls)


def _gd(repo: str) -> str:
    return de.REPOS[repo].git_dir()


# ── happy path ────────────────────────────────────────────────────────────────

def test_deploy_core_ok(state_tmp, monkeypatch):
    fake = _Fake(heads={_gd("core"): "old1234"})
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)

    res = de.run_release(["core"], {"core": "abc1234"})
    assert res.ok
    assert res.repos["core"]["ok"] is True and res.repos["core"]["rolled_back"] is False
    assert res.services["core"]["ok"] is True
    # pin (checkout) + restart de la unit
    assert fake.did("checkout", "abc1234")
    assert fake.did("restart", "capitan-core")
    # versión registrada
    st = de.load_state()
    assert st["repos"]["core"]["status"] == "deployed"
    assert st["last_release"]["ok"] is True


def test_default_services_excluyen_wa(state_tmp, monkeypatch):
    fake = _Fake()
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    res = de.run_release()   # default
    assert set(res.services) == set(de.DEFAULT_SERVICES)
    assert "wa" not in res.services
    assert not fake.did("restart", "capitan-wa")


def test_umbrella_un_ref_para_varios_servicios(state_tmp, monkeypatch):
    # backoffice y bridge comparten el repo umbrella → un solo checkout del umbrella.
    fake = _Fake()
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    res = de.run_release(["backoffice", "bridge"], {"umbrella": "v2"})
    assert res.ok
    checkouts_umbrella = [c for c in fake.calls
                          if "checkout" in c and c[c.index("-C") + 1] == _gd("umbrella")]
    assert len(checkouts_umbrella) == 1   # un único checkout del umbrella
    assert fake.did("restart", "capitan-backoffice")
    assert fake.did("restart", "capitan-bridge")


# ── fallos → rollback ───────────────────────────────────────────────────────────

def test_health_fail_revierte_repo(state_tmp, monkeypatch):
    fake = _Fake(heads={_gd("core"): "good999"})
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: False)   # health siempre falla

    res = de.run_release(["core"], {"core": "bad5678"})
    assert res.ok is False
    assert res.repos["core"]["ok"] is False
    assert res.repos["core"]["rolled_back"] is True
    # rollback hizo checkout del snapshot
    assert fake.did("checkout", "good999")


def test_pin_fail_revierte(state_tmp, monkeypatch):
    fake = _Fake(heads={_gd("core"): "snap111"}, fail=("checkout --quiet bad",))
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    res = de.run_release(["core"], {"core": "bad"})
    assert res.ok is False
    assert res.repos["core"]["rolled_back"] is True


def test_atomicidad_por_repo(state_tmp, monkeypatch):
    # deploy core + backoffice (repos core + umbrella). umbrella health falla, core ok.
    # core (repo independiente) queda desplegado; umbrella revierte.
    fake = _Fake(heads={_gd("core"): "c0", _gd("umbrella"): "u0"})
    monkeypatch.setattr(de, "_run", fake)
    # health: core (8765) ok, backoffice (8080) falla
    monkeypatch.setattr(de, "_http_ok", lambda url, timeout=5.0: "8765" in url)

    res = de.run_release(["core", "backoffice"], {"core": "c1", "umbrella": "u1"})
    assert res.ok is False
    assert res.repos["core"]["ok"] is True            # core sano, no revertido
    assert res.repos["core"]["rolled_back"] is False
    assert res.repos["umbrella"]["ok"] is False
    assert res.repos["umbrella"]["rolled_back"] is True
    assert fake.did("checkout", "u0")                 # umbrella revertido a su snapshot
    assert res.services["core"]["ok"] is True
    assert res.services["backoffice"]["ok"] is False


def test_install_solo_si_hay_requirements(state_tmp, monkeypatch):
    # ear no tiene requirements → no se llama pip; core sí.
    fake = _Fake()
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    de.run_release(["ear"], {"ear": "e1"})
    assert not fake.did("install")
    de.run_release(["core"], {"core": "c1"})
    assert fake.did("install", "core/requirements.txt")


# ── resolve / parsing ───────────────────────────────────────────────────────────

def test_resolve_default():
    svcs, refs = de.resolve(None, None)
    assert svcs == de.DEFAULT_SERVICES
    assert set(refs) == {"core", "ear", "umbrella"}   # repos de los servicios default
    assert all(v is None for v in refs.values())


def test_resolve_servicio_desconocido():
    with pytest.raises(ValueError):
        de.resolve(["nope"], None)


def test_resolve_repo_desconocido():
    with pytest.raises(ValueError):
        de.resolve(["core"], {"nope": "x"})


def test_parse_refs():
    assert de._parse_refs(["core=abc", "umbrella=v1.2"]) == {"core": "abc", "umbrella": "v1.2"}


def test_parse_refs_invalid():
    with pytest.raises(SystemExit):
        de._parse_refs(["coreabc"])


def test_emit_recibe_lineas(state_tmp, monkeypatch):
    fake = _Fake()
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    lines: list[str] = []
    res = de.run_release(["bridge"], emit=lines.append)
    assert lines == res.log and len(lines) > 0


# ── Versionado semver (tag_release) ───────────────────────────────────────────

def test_next_version():
    assert de._next_version(None, "patch") == "v0.1.0"
    assert de._next_version((1, 2, 3), "patch") == "v1.2.4"
    assert de._next_version((1, 2, 3), "minor") == "v1.3.0"
    assert de._next_version((1, 2, 3), "major") == "v2.0.0"


def test_repo_slug_parsing(monkeypatch):
    cases = {
        "git@github.com:mblasi/home-agents-core.git": "mblasi/home-agents-core",
        "https://github.com/mblasi/home-agents.git": "mblasi/home-agents",
        "git@github.com:mblasi/home-agents-ear": "mblasi/home-agents-ear",
    }
    for url, slug in cases.items():
        monkeypatch.setattr(de, "_run", lambda *a, **k: de.RunResult(True, url))
        assert de._repo_slug("/x", de._noop_emit) == slug


def test_tag_release_disabled_no_tag(monkeypatch):
    # TAG_RELEASES off + sha sin tag previo → no crea tag.
    monkeypatch.setattr(de, "TAG_RELEASES", False)
    monkeypatch.setattr(de, "_run", lambda *a, **k: de.RunResult(True, ""))  # tag --points-at vacío
    out = de.tag_release("core", "abc1234", de._noop_emit)
    assert out["tag"] is None and out["created"] is False


def test_tag_release_reusa_tag_existente(monkeypatch):
    # el sha ya tiene un tag semver → lo reusa, no crea otro (aunque TAG_RELEASES on).
    monkeypatch.setattr(de, "TAG_RELEASES", True)

    def _fake(args, emit, **k):
        if "--points-at" in args:
            return de.RunResult(True, "v1.4.0\n")
        if "get-url" in args:
            return de.RunResult(True, "git@github.com:mblasi/home-agents-core.git")
        return de.RunResult(True, "")
    monkeypatch.setattr(de, "_run", _fake)
    out = de.tag_release("core", "abc1234", de._noop_emit)
    assert out["tag"] == "v1.4.0" and out["created"] is False
    assert out["url"] == "https://github.com/mblasi/home-agents-core/releases/tag/v1.4.0"


def test_tag_release_crea_y_pushea(monkeypatch):
    monkeypatch.setattr(de, "TAG_RELEASES", True)
    calls = []

    def _fake(args, emit, **k):
        calls.append(args)
        if "--points-at" in args:
            return de.RunResult(True, "")          # sin tag previo en el sha
        if "--list" in args:
            return de.RunResult(True, "v0.3.1\nv0.3.0\n")  # último = v0.3.1
        if "get-url" in args:
            return de.RunResult(True, "git@github.com:mblasi/home-agents-core.git")
        return de.RunResult(True, "")
    monkeypatch.setattr(de, "_run", _fake)
    out = de.tag_release("core", "deadbee", de._noop_emit)
    assert out["tag"] == "v0.3.2" and out["created"] is True
    assert any("tag" in c and "v0.3.2" in c for c in calls)
    assert any(c[:2] == ["git", "-C"] and "push" in c and "v0.3.2" in c for c in calls)


def test_release_registra_tag_en_estado(state_tmp, monkeypatch):
    monkeypatch.setattr(de, "TAG_RELEASES", True)
    heads = {_gd("core"): "c0"}

    def _fake(args, emit, **k):
        if args[0] == "git" and "-C" in args:
            gd = args[args.index("-C") + 1]
            if "rev-parse" in args:
                return de.RunResult(True, heads.get(gd, "c0"))
            if "checkout" in args:
                heads[gd] = "c1"
            if "--points-at" in args:
                return de.RunResult(True, "")
            if "--list" in args:
                return de.RunResult(True, "v1.0.0")
            if "get-url" in args:
                return de.RunResult(True, "git@github.com:mblasi/home-agents-core.git")
        return de.RunResult(True, "")
    monkeypatch.setattr(de, "_run", _fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    res = de.run_release(["core"], {"core": "c1"})
    assert res.repos["core"]["tag"] == "v1.0.1"
    st = de.load_state()
    assert st["repos"]["core"]["tag"] == "v1.0.1"
    assert "v1.0.1" in st["repos"]["core"]["url"]


# ── Driver cloudrun (T4): deploy GCP desde el Brain ────────────────────────────

class _FakeGcloud:
    """Mock de _run para gcloud: describe→revisión, deploy/update-traffic ok salvo `fail`."""
    def __init__(self, revision="rev-1", fail=()):
        self.revision = revision
        self.fail = set(fail)
        self.calls = []

    def __call__(self, args, emit, *, timeout=300):
        self.calls.append(args)
        joined = " ".join(args)
        for f in self.fail:
            if f in joined:
                return de.RunResult(False, f"fail:{f}")
        if "describe" in args:
            return de.RunResult(True, self.revision)
        return de.RunResult(True, "ok")

    def did(self, *subs):
        return any(all(s in " ".join(c) for s in subs) for c in self.calls)


def test_cloud_release_ok(state_tmp, monkeypatch):
    fake = _FakeGcloud(revision="capitan-cloud-00010")
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    res = de.run_cloud_release(["cloud-bo"])
    assert res.ok and res.services["cloud-bo"]["ok"] is True
    assert fake.did("run", "deploy", "capitan-cloud", "--source")


def test_cloud_release_registra_version_en_estado(state_tmp, monkeypatch):
    # 34.15/34.2: tras un deploy ok, el state guarda la versión (sha de umbrella) que corre en
    # el target cloudrun → la matriz puede mostrar qué versión sirve cloud-bo en GCP.
    fake = _FakeGcloud(revision="capitan-cloud-00010")
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    de.run_cloud_release(["cloud-bo"])
    ci = de.load_state().get("cloud", {}).get("cloud-bo", {})
    assert ci.get("ok") is True
    assert ci.get("version")                 # sha del repo fuente (umbrella)
    assert ci.get("revision") == "capitan-cloud-00010"
    assert ci.get("repo") == "umbrella"


def test_cloud_release_health_fail_rollback(state_tmp, monkeypatch):
    fake = _FakeGcloud(revision="capitan-cloud-prev")
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: False)   # health falla siempre
    res = de.run_cloud_release(["cloud-bo"])
    assert res.ok is False
    assert res.services["cloud-bo"]["rolled_back"] is True
    # rollback a la revisión previa
    assert fake.did("update-traffic", "capitan-cloud-prev=100")
    # el state marca el target como no-ok (no pisa la versión sana con una rota)
    assert de.load_state().get("cloud", {}).get("cloud-bo", {}).get("ok") is False


def test_cloud_release_unknown_target(state_tmp):
    import pytest
    with pytest.raises(ValueError):
        de.run_cloud_release(["nope"])


def test_cloud_deploy_forces_to_latest(state_tmp, monkeypatch):
    # tras el deploy, despinea el tráfico → --to-latest (si no, un rollback previo deja la
    # revisión nueva sin tráfico). Regresión del bug T5.
    fake = _FakeGcloud()
    monkeypatch.setattr(de, "_run", fake)
    monkeypatch.setattr(de, "_http_ok", lambda *a, **k: True)
    de.run_cloud_release(["cloud-bo"])
    assert fake.did("update-traffic", "--to-latest")


# ── Registro TARGETS (34.15): consistencia con el motor ───────────────────────

def test_targets_consistentes_con_el_motor():
    """Cada target declara un comando y params válidos contra los registros del motor."""
    for t in de.TARGETS:
        assert t.repo in de.REPOS, f"{t.id}: repo {t.repo!r} desconocido"
        if t.kind == "service":
            assert t.command == "deploy.release"
            for s in t.params["services"]:
                assert s in de.SERVICES, f"{t.id}: service {s!r} no está en SERVICES"
        elif t.kind == "cloudrun":
            assert t.command == "deploy.cloud"
            for s in t.params["services"]:
                assert s in de.CLOUDRUN_TARGETS, f"{t.id}: {s!r} no es target cloudrun"
        else:
            raise AssertionError(f"{t.id}: kind inesperado {t.kind!r}")

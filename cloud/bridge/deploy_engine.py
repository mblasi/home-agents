"""
core del MOTOR DE DEPLOY (FASE 34) — corre en el SER9, es el ÚNICO backend de deploy.

Principio (FASE 34): existe UN solo motor con la lógica de deploy (snapshot → pin de ref →
install → restart → health-gate → rollback → registro de versión). Lo invocan dos frontends
sin reimplementar nada: el executor del bridge (remoto, comando `deploy.release` del cloud-bo)
y `scripts/deploy.sh` (local, cuando se opera desde la LAN). Ver DECISIONES CONSOLIDADAS en
masterplan/estado.md (D1–D9).

Modelo (Tanda 2): se separan dos conceptos que la Tanda 1 mezclaba —
  - REPO: unidad de VERSIÓN. Un repo git pineable a un ref. Son tres: `core` (submodule),
    `ear` (submodule) y `umbrella` (el repo raíz, que provee backoffice/wa/bridge).
  - SERVICE: unidad de RESTART/HEALTH. Una unit systemd servida por un repo, con su /health y
    sus requirements. Cinco: core, ear(audio_server), backoffice, wa, bridge.

Pin independiente por repo (clave del submodule↔umbrella): `git checkout` del umbrella mueve
SÓLO sus archivos rastreados (backoffice/, wa/, cloud/, scripts/…); NO toca los working dirs de
core/ y ear/ (sólo el puntero de submodule en el índice, que queda como "modified" — cosmético).
Por eso NO se corre `git submodule update`: cada repo se pinea con su propio checkout, sin
acoplarse. Atomicidad POR-REPO (D7): si un servicio falla su health, se revierte SU repo (y se
reinician sus servicios); los otros repos, sanos, quedan.

Sin estado global mutable: los efectos (git, systemctl, http) están aislados en `_run`/`_http_ok`
para mockearlos en los tests.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

REPO_DIR = os.environ.get("REPO_DIR", os.path.expanduser("~/workspace/home-agents"))
PIP = os.environ.get("PIP_BIN", os.path.expanduser("~/home-agents-env/bin/pip"))
STATE_PATH = os.environ.get(
    "DEPLOY_STATE_PATH", os.path.expanduser("~/.local/share/capitan/deploy_state.json"))
HEALTH_RETRIES = int(os.environ.get("DEPLOY_HEALTH_RETRIES", "15"))
HEALTH_BACKOFF = float(os.environ.get("DEPLOY_HEALTH_BACKOFF", "2.0"))
# Versionado formal (FASE 34, D8/34.12): tras un deploy exitoso, crear un tag semver por repo
# y pushearlo (SSH; el SER9 ya pushea por SSH). GATE de seguridad: off por defecto para no crear
# tags reales hasta validarlo. El "Release" formal de GitHub (notas) requiere token y se agrega
# aparte; el tag pusheado ya es un ref inmutable y trazable, y GitHub lo muestra.
TAG_RELEASES = os.environ.get("DEPLOY_TAG_RELEASES", "false").lower() in ("1", "true", "yes")

LogEmit = Callable[[str], None]


def _noop_emit(_line: str) -> None:
    pass


# ── Ejecución de subprocesos (aislada para tests) ─────────────────────────────

@dataclass
class RunResult:
    ok: bool
    output: str = ""


def _run(args: list[str], emit: LogEmit, *, timeout: int = 300) -> RunResult:
    """Corre un subproceso (lista de args, NUNCA shell), emite el comando + su salida en vivo
    y devuelve (ok, output)."""
    import subprocess
    emit(f"$ {' '.join(args)}")
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        emit(f"  ✗ timeout tras {timeout}s")
        return RunResult(False, f"timeout: {' '.join(args)}")
    except Exception as exc:
        emit(f"  ✗ {type(exc).__name__}: {exc}")
        return RunResult(False, str(exc))
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.splitlines():
        emit(f"  {line}")
    if proc.returncode != 0:
        emit(f"  ✗ rc={proc.returncode}")
    return RunResult(proc.returncode == 0, out)


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        return 200 <= r.status_code < 400
    except Exception:
        return False


# ── Repos (unidad de versión) ─────────────────────────────────────────────────

@dataclass
class Repo:
    """Repo git pineable a un ref. `subpath` vacío = umbrella (REPO_DIR); si no, submodule."""
    name: str
    subpath: str

    def git_dir(self) -> str:
        return os.path.join(REPO_DIR, self.subpath) if self.subpath else REPO_DIR

    def head(self, emit: LogEmit = _noop_emit) -> Optional[str]:
        r = _run(["git", "-C", self.git_dir(), "rev-parse", "--short", "HEAD"], emit, timeout=15)
        return r.output.strip() if r.ok else None

    def pin(self, ref: Optional[str], emit: LogEmit) -> bool:
        """fetch + checkout del ref pedido (ref None = HEAD remoto de main). Independiente: no
        corre `git submodule update`, así pinar el umbrella no pisa core/ear (ni viceversa)."""
        gd = self.git_dir()
        if not _run(["git", "-C", gd, "fetch", "--tags", "--quiet", "origin"], emit, timeout=120).ok:
            return False
        return _run(["git", "-C", gd, "checkout", "--quiet", ref or "origin/main"],
                    emit, timeout=60).ok


REPOS: dict[str, Repo] = {
    "umbrella": Repo("umbrella", ""),
    "core": Repo("core", "core"),
    "ear": Repo("ear", "ear"),
}


# ── Services (unidad de restart/health) ───────────────────────────────────────

@dataclass
class Service:
    """Unit systemd servida por un repo, con su /health opcional y requirements opcionales."""
    name: str
    unit: str
    repo: str
    health_url: Optional[str] = None
    requirements: Optional[str] = None   # relativo a REPO_DIR; instalar si el repo cambió

    def install(self, emit: LogEmit) -> bool:
        if not self.requirements:
            return True
        return _run([PIP, "install", "-q", "-r", os.path.join(REPO_DIR, self.requirements)],
                    emit, timeout=300).ok

    def restart(self, emit: LogEmit) -> bool:
        return _run(["systemctl", "--user", "restart", self.unit], emit, timeout=60).ok

    def health(self, emit: LogEmit) -> bool:
        if not _run(["systemctl", "--user", "is-active", "--quiet", self.unit],
                    emit, timeout=15).ok:
            emit(f"  ✗ {self.unit} no está active")
            return False
        if not self.health_url:
            return True
        for _ in range(HEALTH_RETRIES):
            if _http_ok(self.health_url):
                emit(f"  ✓ health OK ({self.health_url})")
                return True
            time.sleep(HEALTH_BACKOFF)
        emit(f"  ✗ health NO responde tras {HEALTH_RETRIES} intentos ({self.health_url})")
        return False


SERVICES: dict[str, Service] = {
    "core": Service("core", "capitan-core", "core",
                    "http://localhost:8765/health", "core/requirements.txt"),
    "ear": Service("ear", "capitan-audio-server", "ear", "http://localhost:8766/health"),
    "backoffice": Service("backoffice", "capitan-backoffice", "umbrella",
                          "http://localhost:8080/", "backoffice/requirements.txt"),
    "wa": Service("wa", "capitan-wa", "umbrella"),
    "bridge": Service("bridge", "capitan-bridge", "umbrella"),
}

# Servicios por defecto de un release "todo a main". Se excluyen:
#  - wa: restart caro (reconectar WhatsApp puede pedir re-escanear el QR).
#  - bridge: FOOTGUN — si el deploy lo invoca el propio bridge (executor remoto), reiniciar
#    capitan-bridge mata el proceso que está corriendo el deploy a mitad (auto-suicidio, no
#    reporta resultado). Desplegar bridge requiere restart DESACOPLADO (systemd-run diferido);
#    se resuelve en una tanda siguiente. Hasta entonces, bridge sólo por deploy.sh local.
# Ambos se pueden incluir explícitamente en `services`.
DEFAULT_SERVICES = ["core", "ear", "backoffice"]


def services_of_repo(repo: str) -> list[str]:
    return [n for n, s in SERVICES.items() if s.repo == repo]


# ── Versionado formal (semver + tag) ──────────────────────────────────────────

import re as _re

_SEMVER_TAG = _re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _repo_slug(git_dir: str, emit: LogEmit) -> Optional[str]:
    """owner/repo a partir del remote origin (git@github.com:owner/repo.git o https://…)."""
    r = _run(["git", "-C", git_dir, "remote", "get-url", "origin"], emit, timeout=15)
    if not r.ok:
        return None
    url = r.output.strip()
    m = _re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None


def _latest_semver(git_dir: str, emit: LogEmit) -> Optional[tuple[int, int, int]]:
    """Mayor tag vX.Y.Z del repo, o None si no hay ninguno."""
    r = _run(["git", "-C", git_dir, "tag", "--list", "v*.*.*"], emit, timeout=15)
    if not r.ok:
        return None
    best: Optional[tuple[int, int, int]] = None
    for line in r.output.splitlines():
        m = _SEMVER_TAG.match(line.strip())
        if m:
            v = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if best is None or v > best:
                best = v
    return best


def _tag_at(git_dir: str, sha: str, emit: LogEmit) -> Optional[str]:
    """Tag semver que ya apunta a `sha` (para no re-tagear un sha ya versionado)."""
    r = _run(["git", "-C", git_dir, "tag", "--points-at", sha], emit, timeout=15)
    if not r.ok:
        return None
    for line in r.output.splitlines():
        if _SEMVER_TAG.match(line.strip()):
            return line.strip()
    return None


def _next_version(latest: Optional[tuple[int, int, int]], bump: str) -> str:
    """Siguiente semver desde `latest` (None = primer release v0.1.0). bump ∈ patch|minor|major."""
    if latest is None:
        return "v0.1.0"
    x, y, z = latest
    if bump == "major":
        return f"v{x + 1}.0.0"
    if bump == "minor":
        return f"v{x}.{y + 1}.0"
    return f"v{x}.{y}.{z + 1}"


def tag_release(repo_name: str, sha: str, emit: LogEmit, bump: str = "patch") -> dict:
    """Crea (si TAG_RELEASES) un tag semver para `sha` y lo pushea por SSH. Si el sha ya tiene un
    tag semver, lo reusa (no re-tagea). Devuelve {tag, url, created}; degradación elegante si el
    versionado está apagado o el push falla (no rompe el deploy)."""
    git_dir = REPOS[repo_name].git_dir()
    slug = _repo_slug(git_dir, emit)
    url_for = lambda t: (f"https://github.com/{slug}/releases/tag/{t}" if slug else None)

    existing = _tag_at(git_dir, sha, emit)
    if existing:
        return {"tag": existing, "url": url_for(existing), "created": False}
    if not TAG_RELEASES:
        return {"tag": None, "url": None, "created": False}

    tag = _next_version(_latest_semver(git_dir, emit), bump)
    if not _run(["git", "-C", git_dir, "tag", "-a", tag, "-m", f"release {tag}", sha], emit).ok:
        emit(f"  ✗ no se pudo crear el tag {tag}")
        return {"tag": None, "url": None, "created": False}
    if not _run(["git", "-C", git_dir, "push", "origin", tag], emit, timeout=60).ok:
        emit(f"  ✗ no se pudo pushear el tag {tag} (¿credencial?)")
        return {"tag": tag, "url": url_for(tag), "created": False}
    emit(f"  ✓ release {repo_name} {tag} → {url_for(tag)}")
    return {"tag": tag, "url": url_for(tag), "created": True}


# ── Estado persistido (matriz de versiones) ───────────────────────────────────

def load_state() -> dict:
    try:
        return json.loads(Path(STATE_PATH).read_text(encoding="utf-8"))
    except Exception:
        return {"repos": {}, "services": {}, "last_release": None}


def save_state(state: dict) -> None:
    p = Path(STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Orquestador del release ───────────────────────────────────────────────────

@dataclass
class ReleaseResult:
    ok: bool
    repos: dict[str, dict] = field(default_factory=dict)      # repo → {ok, version, rolled_back}
    services: dict[str, dict] = field(default_factory=dict)   # svc → {ok, repo}
    log: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "repos": self.repos, "services": self.services, "log": self.log}


def resolve(services: Optional[list[str]], repo_refs: Optional[dict[str, Optional[str]]]
            ) -> tuple[list[str], dict[str, Optional[str]]]:
    """Normaliza la entrada del release a (servicios, refs por repo a pinar).

    - services None → DEFAULT_SERVICES (core/ear/backoffice/bridge; wa excluido).
    - repo_refs None → {} → todos los repos involucrados a origin/main.
    Los repos a pinar son los de los servicios pedidos UNIÓN los de repo_refs explícitos; cada
    repo sin ref explícito queda en None (origin/main)."""
    svcs = list(services) if services else list(DEFAULT_SERVICES)
    for s in svcs:
        if s not in SERVICES:
            raise ValueError(f"servicio de deploy desconocido: {s!r} (conocidos: {sorted(SERVICES)})")
    refs = dict(repo_refs or {})
    for r in refs:
        if r not in REPOS:
            raise ValueError(f"repo desconocido: {r!r} (conocidos: {sorted(REPOS)})")
    repos = {SERVICES[s].repo for s in svcs} | set(refs)
    return svcs, {r: refs.get(r) for r in repos}


def run_release(services: Optional[list[str]] = None,
                repo_refs: Optional[dict[str, Optional[str]]] = None,
                emit: Optional[LogEmit] = None,
                bumps: Optional[dict[str, str]] = None) -> ReleaseResult:
    """Despliega los `services` pedidos pinando sus repos a `repo_refs` (default origin/main).

    Flujo: snapshot de la versión de cada repo → pin de todos los repos → por repo, install +
    restart + health-gate de SUS servicios; si alguno falla, rollback de ESE repo a su snapshot
    y restart de sus servicios (atomicidad por-repo, D7). Los repos sanos quedan desplegados y,
    si TAG_RELEASES, se tagean (semver; `bumps` por repo, default patch).
    `emit` recibe logs incrementales (D5); si None se acumulan en el resultado.
    """
    bumps = bumps or {}
    svcs, refs = resolve(services, repo_refs)
    result = ReleaseResult(ok=True)

    def _emit(line: str) -> None:
        result.log.append(line)
        if emit:
            emit(line)

    state = load_state()
    snapshots = {r: REPOS[r].head(_emit) for r in refs}
    _emit(f"=== release: servicios={svcs} repos={ {r: refs[r] or 'origin/main' for r in refs} } ===")

    # Pin de todos los repos pedidos (independiente, sin submodule update).
    pinned: dict[str, bool] = {}
    for r in refs:
        _emit(f"--- pin {r}: {snapshots[r] or '?'} → {refs[r] or 'origin/main'}")
        pinned[r] = REPOS[r].pin(refs[r], _emit)

    # Por repo: desplegar sus servicios (de los pedidos); si algo falla, revertir el repo.
    for r in refs:
        repo_svcs = [s for s in svcs if SERVICES[s].repo == r]
        repo_ok = pinned[r]
        if not repo_ok:
            _emit(f"  ✗ pin de {r} falló")
        for s in repo_svcs if repo_ok else []:
            svc = SERVICES[s]
            if not (svc.install(_emit) and svc.restart(_emit) and svc.health(_emit)):
                _emit(f"  ✗ servicio {s} falló")
                repo_ok = False
                break

        if repo_ok:
            ver = REPOS[r].head(_emit)
            # Versionado formal (D8/34.12): tag semver del sha desplegado (gated por TAG_RELEASES;
            # reusa el tag si el sha ya estaba versionado). No rompe el deploy si falla.
            rel = tag_release(r, ver, _emit, bump=bumps.get(r, "patch")) if ver else {}
            result.repos[r] = {"ok": True, "version": ver, "rolled_back": False,
                               "tag": rel.get("tag"), "url": rel.get("url")}
            for s in repo_svcs:
                result.services[s] = {"ok": True, "repo": r}
            _emit(f"  ✓ {r} desplegado y sano ({ver}{' ' + rel['tag'] if rel.get('tag') else ''})")
        else:
            result.ok = False
            _emit(f"  ↩ rollback {r} → {snapshots[r] or '?'}")
            rb = REPOS[r].pin(snapshots[r], _emit) if snapshots[r] else False
            restored = rb
            for s in repo_svcs:
                if not (SERVICES[s].install(_emit) and SERVICES[s].restart(_emit)
                        and SERVICES[s].health(_emit)):
                    restored = False
            ver = REPOS[r].head(_emit)
            result.repos[r] = {"ok": False, "version": ver, "rolled_back": rb,
                               "restored": restored}
            for s in repo_svcs:
                result.services[s] = {"ok": False, "repo": r}
            _emit(f"  {'↩ revertido a' if restored else '✗ rollback NO sano en'} {r} ({ver})")

    # Persistir la matriz de versiones + último release.
    for r, info in result.repos.items():
        state.setdefault("repos", {})[r] = {
            "version": info["version"],
            "tag": info.get("tag"),
            "url": info.get("url"),
            "status": "deployed" if info["ok"] else ("rolled_back" if info.get("restored") else "broken"),
            "ts": time.time()}
    for s, info in result.services.items():
        state.setdefault("services", {})[s] = {
            "version": result.repos[info["repo"]]["version"], "ok": info["ok"], "ts": time.time()}
    state["last_release"] = {"ts": time.time(), "ok": result.ok,
                             "services": svcs, "refs": {r: refs[r] for r in refs}}
    save_state(state)
    return result


# ── Driver cloudrun (GCP, FASE 34 T4 / D2) ────────────────────────────────────
# El SER9 despliega Cloud Run con `gcloud run deploy --source` (egress a Google, saliente),
# usando la SA de deploy (D9: GOOGLE_APPLICATION_CREDENTIALS apunta a la key en el SER9).
# Health-gate = curl a la URL pública. Rollback = update-traffic a la revisión previa (Cloud Run
# conserva revisiones). NO pasa por el bridge para sí mismo (circularidad, D4): el deploy del
# cloud-bo lo dispara igual el SER9, y si rompe, el rollback a la revisión previa lo hace el SER9.

GCLOUD = os.environ.get("GCLOUD_BIN", "gcloud")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "capitan-495518")


@dataclass
class CloudRunTarget:
    """Servicio de Cloud Run desplegable desde el SER9. `source` es el dir (relativo a REPO_DIR)
    que contiene el Dockerfile; `health_url` es la URL pública para el health-gate."""
    name: str
    service: str
    source: str
    region: str
    health_url: str
    source_repo: str = "umbrella"   # repo del que sale el build → sha que corre el target

    def _src(self) -> str:
        return os.path.join(REPO_DIR, self.source)

    def active_revision(self, emit: LogEmit) -> Optional[str]:
        r = _run([GCLOUD, "run", "services", "describe", self.service,
                  "--project", GCP_PROJECT, "--region", self.region,
                  "--format=value(status.latestReadyRevisionName)"], emit, timeout=60)
        return r.output.strip() if r.ok and r.output.strip() else None

    def deploy(self, emit: LogEmit) -> bool:
        if not _run([GCLOUD, "run", "deploy", self.service, "--source", self._src(),
                     "--project", GCP_PROJECT, "--region", self.region, "--quiet"],
                    emit, timeout=600).ok:
            return False
        # Forzar tráfico a la última revisión: tras un rollback el servicio queda con el tráfico
        # PINEADO a una revisión vieja (update-traffic --to-revisions), y `deploy` NO lo mueve
        # solo → la revisión nueva quedaría sin tráfico. --to-latest despinea y sirve la nueva.
        return _run([GCLOUD, "run", "services", "update-traffic", self.service,
                     "--project", GCP_PROJECT, "--region", self.region, "--to-latest", "--quiet"],
                    emit, timeout=120).ok

    def health(self, emit: LogEmit) -> bool:
        for _ in range(HEALTH_RETRIES):
            if _http_ok(self.health_url):
                emit(f"  ✓ health OK ({self.health_url})")
                return True
            time.sleep(HEALTH_BACKOFF)
        emit(f"  ✗ health NO responde ({self.health_url})")
        return False

    def rollback(self, revision: Optional[str], emit: LogEmit) -> bool:
        if not revision:
            emit("  ✗ sin revisión previa para revertir")
            return False
        emit(f"  ↩ rollback {self.name} → {revision}")
        return _run([GCLOUD, "run", "services", "update-traffic", self.service,
                     "--project", GCP_PROJECT, "--region", self.region,
                     f"--to-revisions={revision}=100", "--quiet"], emit, timeout=120).ok


CLOUDRUN_TARGETS: dict[str, CloudRunTarget] = {
    "cloud-bo": CloudRunTarget(
        "cloud-bo", "capitan-cloud", "cloud", "southamerica-east1",
        os.environ.get("CLOUD_BO_URL",
                       "https://capitan-cloud-606511873514.southamerica-east1.run.app") + "/"),
}


# ── Targets desplegables (vista de operación unificada, 34.15) ─────────────────
# Un TARGET es "algo que corre en algún lado y tiene una versión". Unifica services del SER9,
# Cloud Run y satélites bajo una sola operatoria: la matriz muestra una fila por target y un
# botón que elige el comando solo. El snapshot y los dos frontends consumen esta lista; los
# satélites NO están acá (son dinámicos: uno por panel, los agrega el snapshot desde /nodes).
@dataclass
class Target:
    id: str
    label: str
    where: str          # "SER9" | "GCP"
    repo: str           # repo fuente (para la última versión disponible + link)
    kind: str           # "service" | "cloudrun"
    command: str        # tipo de comando que lo despliega
    params: dict        # params del comando (qué desplegar)
    advanced: bool = False   # wa/bridge: ocultos en la vista normal

TARGETS: list[Target] = [
    Target("core",         "core",         "SER9", "core",     "service",  "deploy.release", {"services": ["core"]}),
    Target("audio_server", "audio_server", "SER9", "ear",      "service",  "deploy.release", {"services": ["ear"]}),
    Target("backoffice",   "backoffice",   "SER9", "umbrella", "service",  "deploy.release", {"services": ["backoffice"]}),
    Target("cloud-bo",     "cloud-bo",     "GCP",  "umbrella", "cloudrun", "deploy.cloud",   {"services": ["cloud-bo"]}),
    Target("wa",           "wa",           "SER9", "umbrella", "service",  "deploy.release", {"services": ["wa"]},     advanced=True),
    Target("bridge",       "bridge",       "SER9", "umbrella", "service",  "deploy.release", {"services": ["bridge"]}, advanced=True),
]


def run_cloud_release(targets: list[str], emit: Optional[LogEmit] = None) -> ReleaseResult:
    """Despliega targets de Cloud Run (cloud-bo, …) por-target con health-gate y rollback a la
    revisión previa si falla. Atomicidad por-target (D7). Reusa ReleaseResult (campo `services`)."""
    result = ReleaseResult(ok=True)
    state = load_state()

    def _emit(line: str) -> None:
        result.log.append(line)
        if emit:
            emit(line)

    for name in targets:
        if name not in CLOUDRUN_TARGETS:
            raise ValueError(f"target cloudrun desconocido: {name!r} (conocidos: {sorted(CLOUDRUN_TARGETS)})")
        t = CLOUDRUN_TARGETS[name]
        # sha del repo fuente (umbrella) en el checkout que se buildea → versión que correrá el target.
        src_sha = REPOS[t.source_repo].head(_emit) if t.source_repo in REPOS else None
        prev = t.active_revision(_emit)
        _emit(f"=== deploy cloudrun {name} ({t.service}) — revisión previa {prev or '?'} ===")
        ok = t.deploy(_emit) and t.health(_emit)
        rev = t.active_revision(_emit) if ok else prev
        if ok:
            tagi = _tag_at(REPOS[t.source_repo].git_dir(), src_sha, _emit) if src_sha else None
            slug = _repo_slug(REPOS[t.source_repo].git_dir(), _emit) if t.source_repo in REPOS else None
            url = (f"https://github.com/{slug}/commit/{src_sha}" if slug and src_sha else None)
            result.services[name] = {"ok": True, "revision": rev, "version": src_sha}
            state.setdefault("cloud", {})[name] = {
                "version": src_sha, "tag": tagi, "url": url, "revision": rev,
                "repo": t.source_repo, "ok": True, "ts": time.time()}
            _emit(f"  ✓ {name} desplegado y sano ({src_sha or rev or '?'})")
        else:
            result.ok = False
            rb = t.rollback(prev, _emit)
            restored = rb and t.health(_emit)
            result.services[name] = {"ok": False, "rolled_back": rb, "restored": restored}
            ci = state.setdefault("cloud", {}).setdefault(name, {})
            ci.update({"ok": False, "ts": time.time(), "revision": prev})
            _emit(f"  {'↩ revertido' if restored else '✗ rollback NO sano'} en {name}")
    save_state(state)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_refs(items: list[str]) -> dict[str, Optional[str]]:
    """--ref core=abc123 --ref umbrella=v1.2 → {'core': 'abc123', 'umbrella': 'v1.2'}."""
    out: dict[str, Optional[str]] = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"--ref inválido (esperado repo=ref): {it!r}")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip() or None
    return out


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Motor de deploy del SER9 (FASE 34)")
    ap.add_argument("--service", action="append", default=[], metavar="name",
                    help=f"servicio a desplegar {sorted(SERVICES)}; default {DEFAULT_SERVICES}")
    ap.add_argument("--ref", action="append", default=[], metavar="repo=ref",
                    help=f"pin de ref por repo {sorted(REPOS)}; default HEAD remoto de main")
    ap.add_argument("--json", action="store_true", help="emitir el resultado como JSON al final")
    args = ap.parse_args(argv)

    res = run_release(args.service or None, _parse_refs(args.ref) or None,
                      emit=lambda l: print(l, flush=True))
    if args.json:
        print(json.dumps(res.as_dict(), ensure_ascii=False))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

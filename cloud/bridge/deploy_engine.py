"""
core del MOTOR DE DEPLOY (FASE 34) — corre en el SER9, es el ÚNICO backend de deploy.

Principio (FASE 34): existe UN solo motor con la lógica de deploy (snapshot → pin de ref →
install → restart → health-gate → rollback → registro de versión). Lo invocan dos frontends
sin reimplementar nada: el executor del bridge (remoto, comando `deploy.release` del cloud-bo)
y `scripts/deploy.sh` (local, cuando se opera desde la LAN). Ver DECISIONES CONSOLIDADAS en
masterplan/estado.md (D1–D6).

Esta tanda implementa el dominio SER9 (driver `ser9-service`): los servicios que corren en el
LXC y se versionan por submodule (core, ear/audio_server) o por el umbrella (backoffice, wa,
bridge). Los drivers `panel` (NSPanels) y `cloudrun` (GCP) se registran como pendientes y se
implementan en tandas siguientes.

Diseño:
  - Cada componente desplegable es un TARGET con un driver. El driver expone la misma interfaz:
    current_version() → str | None, deploy(refs, emit), health() → bool, rollback(snapshot, emit).
  - `run_release` orquesta: snapshot de versiones actuales → deploy → health-gate → si falla,
    rollback al snapshot. Emite logs incrementales por un callback (D5: feedback en vivo).
  - El estado (matriz dispositivo×componente→versión + último release) se persiste local en el
    SER9 (fuente de verdad) y un subconjunto viaja al snapshot del bridge (D6).

Sin estado global mutable: el motor es invocable por CLI o importable; los efectos (git,
systemctl, http) están aislados en helpers mockeables para los tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

REPO_DIR = os.environ.get("REPO_DIR", os.path.expanduser("~/workspace/home-agents"))
PIP = os.environ.get("PIP_BIN", os.path.expanduser("~/home-agents-env/bin/pip"))
STATE_PATH = os.environ.get(
    "DEPLOY_STATE_PATH", os.path.expanduser("~/.local/share/capitan/deploy_state.json"))
# Health-gate: reintentos hasta declarar sano (audio_server tarda en cargar whisper).
HEALTH_RETRIES = int(os.environ.get("DEPLOY_HEALTH_RETRIES", "15"))
HEALTH_BACKOFF = float(os.environ.get("DEPLOY_HEALTH_BACKOFF", "2.0"))

# Emisor de logs incremental: el orquestador empuja líneas; el invocador decide qué hacer con
# ellas (postear append-only a Firestore desde el bridge, imprimir en la consola local, etc.).
LogEmit = Callable[[str], None]


def _noop_emit(_line: str) -> None:
    pass


# ── Ejecución de subprocesos (aislada para tests) ─────────────────────────────

@dataclass
class RunResult:
    ok: bool
    output: str = ""


def _run(args: list[str], emit: LogEmit, *, timeout: int = 300, cwd: Optional[str] = None
         ) -> RunResult:
    """Corre un subproceso (lista de args, NUNCA shell), emite el comando + su salida en vivo
    y devuelve (ok, output). El output se acumula para el resultado final del comando."""
    emit(f"$ {' '.join(args)}")
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        emit(f"  ✗ timeout tras {timeout}s")
        return RunResult(False, f"timeout: {' '.join(args)}")
    except Exception as exc:  # binario ausente, etc.
        emit(f"  ✗ {type(exc).__name__}: {exc}")
        return RunResult(False, str(exc))
    out = (proc.stdout or "") + (proc.stderr or "")
    for line in out.splitlines():
        emit(f"  {line}")
    if proc.returncode != 0:
        emit(f"  ✗ rc={proc.returncode}")
    return RunResult(proc.returncode == 0, out)


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    """GET a una URL de health; True si responde 2xx/3xx. requests se importa local para no
    acoplar el import del motor (los tests mockean este helper)."""
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        return 200 <= r.status_code < 400
    except Exception:
        return False


# ── Targets y drivers ─────────────────────────────────────────────────────────

@dataclass
class Ser9ServiceTarget:
    """Componente que corre en el SER9, versionado por un submodule (core, ear) o por el
    umbrella (backoffice, wa, bridge), y servido por una unit systemd con un /health opcional.

    - name: id del componente (core, ear, backoffice, wa, bridge).
    - submodule: ruta del submodule que pinea la versión, o None si es código del umbrella.
    - service: unit systemd a reiniciar.
    - health_url: endpoint de readiness, o None si la unit no expone health.
    - requirements: requirements.txt a instalar si cambió (relativo a REPO_DIR), o None.
    """
    name: str
    service: str
    submodule: Optional[str] = None
    health_url: Optional[str] = None
    requirements: Optional[str] = None
    driver: str = "ser9-service"

    # ── versión ───────────────────────────────────────────────────────────────
    def _git_dir(self) -> str:
        return os.path.join(REPO_DIR, self.submodule) if self.submodule else REPO_DIR

    def current_version(self, emit: LogEmit = _noop_emit) -> Optional[str]:
        """SHA corto del ref desplegado (del submodule si aplica, si no del umbrella)."""
        r = _run(["git", "-C", self._git_dir(), "rev-parse", "--short", "HEAD"],
                 emit, timeout=15)
        return r.output.strip() if r.ok else None

    # ── deploy ─────────────────────────────────────────────────────────────────
    def deploy(self, ref: Optional[str], emit: LogEmit) -> bool:
        """Pin del ref pedido (fetch+checkout) en el git dir del componente; reinstala
        requirements si cambiaron; reinicia la unit. ref None = HEAD remoto de main."""
        gd = self._git_dir()
        if not _run(["git", "-C", gd, "fetch", "--tags", "--quiet", "origin"], emit, timeout=120).ok:
            return False
        target = ref or "origin/main"
        before = self.current_version(emit)
        if not _run(["git", "-C", gd, "checkout", "--quiet", target], emit, timeout=60).ok:
            return False
        # Submodule: el umbrella debe quedar apuntando al ref nuevo en el working tree (no
        # commiteamos; el deploy opera sobre el checkout). Para código del umbrella el checkout
        # de arriba ya movió todo.
        after = self.current_version(emit)
        if self.requirements and before != after:
            req = os.path.join(REPO_DIR, self.requirements)
            if not _run([PIP, "install", "-q", "-r", req], emit, timeout=300).ok:
                return False
        return _run(["systemctl", "--user", "restart", self.service], emit, timeout=60).ok

    # ── health ──────────────────────────────────────────────────────────────────
    def health(self, emit: LogEmit) -> bool:
        """is-active de la unit + (si tiene) health-gate HTTP con reintentos."""
        if not _run(["systemctl", "--user", "is-active", "--quiet", self.service],
                    emit, timeout=15).ok:
            emit(f"  ✗ {self.service} no está active")
            return False
        if not self.health_url:
            return True
        for i in range(HEALTH_RETRIES):
            if _http_ok(self.health_url):
                emit(f"  ✓ health OK ({self.health_url})")
                return True
            time.sleep(HEALTH_BACKOFF)
        emit(f"  ✗ health NO responde tras {HEALTH_RETRIES} intentos ({self.health_url})")
        return False

    # ── rollback ─────────────────────────────────────────────────────────────────
    def rollback(self, snapshot_ref: Optional[str], emit: LogEmit) -> bool:
        """Revierte al ref del snapshot (sha capturado antes del deploy) y reinicia."""
        if not snapshot_ref:
            emit("  ✗ sin ref de snapshot para revertir")
            return False
        emit(f"  ↩ rollback de {self.name} a {snapshot_ref}")
        return self.deploy(snapshot_ref, emit)


# Registro de targets del SER9. Los drivers panel/cloudrun se agregan en tandas siguientes.
SER9_TARGETS: dict[str, Ser9ServiceTarget] = {
    "core": Ser9ServiceTarget(
        "core", "capitan-core", submodule="core",
        health_url="http://localhost:8765/health", requirements="core/requirements.txt"),
    "ear": Ser9ServiceTarget(
        "ear", "capitan-audio-server", submodule="ear",
        health_url="http://localhost:8766/health"),
    "backoffice": Ser9ServiceTarget(
        "backoffice", "capitan-backoffice",
        health_url="http://localhost:8080/", requirements="backoffice/requirements.txt"),
    "wa": Ser9ServiceTarget("wa", "capitan-wa"),
    "bridge": Ser9ServiceTarget("bridge", "capitan-bridge"),
}


def get_target(name: str) -> Ser9ServiceTarget:
    if name not in SER9_TARGETS:
        raise ValueError(f"target de deploy desconocido: {name!r} "
                         f"(conocidos: {sorted(SER9_TARGETS)})")
    return SER9_TARGETS[name]


# ── Estado persistido (matriz de versiones) ───────────────────────────────────

def load_state() -> dict:
    try:
        return json.loads(Path(STATE_PATH).read_text(encoding="utf-8"))
    except Exception:
        return {"components": {}, "last_release": None}


def save_state(state: dict) -> None:
    p = Path(STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _record_version(state: dict, name: str, version: Optional[str], status: str) -> None:
    state.setdefault("components", {})[name] = {
        "version": version, "status": status, "ts": time.time()}


# ── Orquestador del release ───────────────────────────────────────────────────

@dataclass
class ReleaseResult:
    ok: bool
    components: dict[str, dict] = field(default_factory=dict)  # name → {ok, version, rolled_back}
    log: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "components": self.components, "log": self.log}


def run_release(targets: list[str], refs: Optional[dict[str, str]] = None,
                emit: Optional[LogEmit] = None) -> ReleaseResult:
    """Despliega los componentes pedidos de forma atómica por-componente: snapshot de la versión
    actual → deploy(ref) → health-gate → si algo falla, rollback de ESE componente a su snapshot.

    refs: name → ref (sha/tag/branch). Ausente = HEAD remoto de main para ese componente.
    emit: callback de log incremental (D5); si None, se acumula en el resultado.
    """
    refs = refs or {}
    result = ReleaseResult(ok=True)

    def _emit(line: str) -> None:
        result.log.append(line)
        if emit:
            emit(line)

    state = load_state()
    for name in targets:
        target = get_target(name)
        snapshot = target.current_version(_emit)
        _emit(f"=== deploy {name} (desde {snapshot or '?'} → {refs.get(name) or 'origin/main'}) ===")
        comp = {"ok": False, "version": None, "rolled_back": False, "snapshot": snapshot}

        deployed = target.deploy(refs.get(name), _emit)
        healthy = deployed and target.health(_emit)

        if healthy:
            comp["ok"] = True
            comp["version"] = target.current_version(_emit)
            _record_version(state, name, comp["version"], "deployed")
            _emit(f"  ✓ {name} desplegado y sano ({comp['version']})")
        else:
            result.ok = False
            _emit(f"  ✗ {name} falló ({'health' if deployed else 'deploy'}) — revirtiendo")
            comp["rolled_back"] = target.rollback(snapshot, _emit)
            restored = target.health(_emit) if comp["rolled_back"] else False
            comp["version"] = target.current_version(_emit)
            _record_version(state, name, comp["version"],
                            "rolled_back" if restored else "broken")
            _emit(f"  {'↩ revertido a' if restored else '✗ rollback NO sano en'} "
                  f"{name} ({comp['version']})")

        result.components[name] = comp

    state["last_release"] = {"ts": time.time(), "ok": result.ok,
                             "targets": targets, "refs": refs}
    save_state(state)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_refs(items: list[str]) -> dict[str, str]:
    """--ref core=abc123 --ref ear=v1.2 → {'core': 'abc123', 'ear': 'v1.2'}."""
    out: dict[str, str] = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"--ref inválido (esperado name=ref): {it!r}")
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Motor de deploy del SER9 (FASE 34)")
    ap.add_argument("targets", nargs="+", help=f"componentes a desplegar {sorted(SER9_TARGETS)}")
    ap.add_argument("--ref", action="append", default=[], metavar="name=ref",
                    help="pin de ref por componente (sha/tag/branch); default HEAD remoto de main")
    ap.add_argument("--json", action="store_true", help="emitir el resultado como JSON al final")
    args = ap.parse_args(argv)

    res = run_release(args.targets, _parse_refs(args.ref), emit=lambda l: print(l, flush=True))
    if args.json:
        print(json.dumps(res.as_dict(), ensure_ascii=False))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

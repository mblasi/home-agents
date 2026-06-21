"""deploy_cli.py — invocador LOCAL de deploy por TARGET (FASE 34, 34.15).

Da, desde la LAN (Claude / operador), EXACTAMENTE el mismo camino que el cloud-bo remoto:
resuelve un nombre de target → el comando tipado que emite el cloud-bo (deploy.release /
deploy.cloud / deploy.satellites) y lo corre con `validate_command` + `executor.execute` —
el mismo funnel que el bridge usa al desencolar un comando de la nube. No reimplementa nada:
la lógica vive en el motor (deploy_engine) y el contrato en commands.py.

Targets (mismos que muestra la matriz del cloud-bo):
  core | audio_server | backoffice | wa | bridge   (services del Brain → deploy.release)
  cloud-bo                                          (Cloud Run        → deploy.cloud)
  panels | <node_id> (ej. nspanel-comedor)          (satélites        → deploy.satellites)
  (sin target)                                      → deploy.release de los services default

Uso:
  python deploy_cli.py <target> [--ref repo=ref ...] [--json]
  python deploy_cli.py                       # services default a HEAD de main
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))            # deploy_engine, executor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # app.commands

import deploy_engine as de  # noqa: E402
import executor  # noqa: E402
from app.commands import CommandError, validate_command  # noqa: E402


def _static_targets() -> dict[str, "de.Target"]:
    return {t.id: t for t in de.TARGETS}


def resolve_target(name: str | None, refs: dict[str, str] | None) -> tuple[str, dict]:
    """target → (cmd_type, params), con el MISMO mapeo que usa el cloud-bo (registro TARGETS).

    Sin name → deploy.release de los services default (todo a HEAD de main).
    Un id de la matriz → su comando+params. `panels`/`*` → todos los paneles. Cualquier otro
    nombre se trata como node_id de un panel (deploy.satellites). Lanza ValueError si el nombre
    no es ni un target conocido ni un id de panel plausible (evita que un typo dispare un no-op)."""
    refs = refs or {}
    if not name:
        params: dict = {}
        if refs:
            params.update(refs)
        return "deploy.release", params

    targets = _static_targets()
    if name in targets:
        t = targets[name]
        params = dict(t.params)
        if t.command == "deploy.release" and refs:
            params.update(refs)            # core_ref / ear_ref / umbrella_ref
        return t.command, params

    if name in ("panels", "all-panels", "*", "all"):
        return "deploy.satellites", {"node_id": "*"}

    # node_id de un panel: aceptamos el prefijo habitual o "panel:<id>"
    node = name[len("panel:"):] if name.startswith("panel:") else name
    if node.startswith("nspanel-") or node.startswith("panel-"):
        return "deploy.satellites", {"node_id": node}

    valid = sorted(targets) + ["panels", "<node_id> (nspanel-...)"]
    raise ValueError(f"target desconocido: {name!r}. Válidos: {valid}")


def run(name: str | None, refs: dict[str, str] | None, *, emit=print) -> "executor.ExecResult":
    cmd_type, params = resolve_target(name, refs)
    params = validate_command(cmd_type, params)          # mismo gate que la nube + el bridge
    emit(f"=== {cmd_type} {params} ===")
    return executor.execute(cmd_type, params, emit=emit)


def _parse_refs(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items:
        if "=" not in it:
            raise SystemExit(f"--ref inválido (esperado repo=ref): {it!r}")
        k, v = it.split("=", 1)
        # core/ear/umbrella → core_ref/ear_ref/umbrella_ref (params de deploy.release)
        out[f"{k.strip()}_ref"] = v.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Deploy por target (mismo camino que el cloud-bo)")
    ap.add_argument("target", nargs="?", default=None,
                    help="core|audio_server|backoffice|wa|bridge|cloud-bo|panels|<node_id>")
    ap.add_argument("--ref", action="append", default=[], metavar="repo=ref",
                    help="pin de ref por repo (solo deploy.release)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        res = run(args.target, _parse_refs(args.ref), emit=lambda l: print(l, flush=True))
    except (ValueError, CommandError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    if args.json:
        import json
        print(json.dumps({"ok": res.ok, "output": res.output, "error": res.error},
                         ensure_ascii=False))
    else:
        print(("✓ " + (res.output or "OK")) if res.ok else ("✗ " + (res.error or "fallo")))
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

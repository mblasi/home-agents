#!/usr/bin/env python3
"""
Detecta inconsistencias en masterplan/estado.md:

  1. Tareas [x] bajo un header "#### Pendiente" (o similar)
  2. Tareas [ ] bajo un header "#### Completado" (o similar)
  3. El `Estado:` de cada `### FASE` desincronizado con sus checkboxes:
       - todas las tareas [x] (0 pendientes) pero Estado no es COMPLETA
       - hay tareas [x] y [ ] (avance parcial) pero Estado dice "Pendiente" (debería ser EN CURSO)
     (COMPLETA con algún [ ] está permitido — es la convención "COMPLETA (X postergada)".)

Solo reporta los headers Completado/Pendiente — el resto de #### son sección narrativa válida.

Uso:
  python scripts/lint_estado.py          # imprime errores y sale con código 1 si hay
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

ESTADO = Path(__file__).parent.parent / "masterplan" / "estado.md"

_SECTION_HEADER = re.compile(r"^#{1,3}\s")       # ###, ##, # → resetea contexto
_SUB_HEADER     = re.compile(r"^####\s+(.+)")
_TASK_DONE      = re.compile(r"^\s*-\s+\[x\]", re.IGNORECASE)
_TASK_OPEN      = re.compile(r"^\s*-\s+\[\s\]")

_PENDIENTE_RE   = re.compile(r"pendiente", re.IGNORECASE)
_COMPLETADO_RE  = re.compile(r"completado|ya implementado", re.IGNORECASE)

_PHASE_HEADER   = re.compile(r"^###\s+(FASE\s+[\d.]+)\b\s*-?\s*(.*)")
_ESTADO_LINE    = re.compile(r"^Estado:\s*(.+)", re.IGNORECASE)


def lint_phase_status(lines: list[str]) -> list[str]:
    """Valida que el `Estado:` de cada FASE coincida con el avance de sus checkboxes."""
    errors: list[str] = []
    phases: list[dict] = []
    cur: dict | None = None
    for i, line in enumerate(lines, 1):
        m = _PHASE_HEADER.match(line)
        if m:
            cur = {"id": m.group(1), "name": m.group(2).strip()[:40], "line": i,
                   "estado": None, "estado_line": 0, "done": 0, "pend": 0}
            phases.append(cur)
            continue
        if cur is None:
            continue
        em = _ESTADO_LINE.match(line)
        if em and cur["estado"] is None:
            cur["estado"] = em.group(1).strip()
            cur["estado_line"] = i
        elif _TASK_DONE.match(line):
            cur["done"] += 1
        elif _TASK_OPEN.match(line):
            cur["pend"] += 1

    for p in phases:
        est = (p["estado"] or "").upper()
        if p["estado"] is None or (p["done"] == 0 and p["pend"] == 0):
            continue   # fases narrativas / sin tareas
        completa = est.startswith("COMPLETA")
        en_curso = "EN CURSO" in est
        if p["pend"] == 0 and p["done"] > 0 and not completa:
            errors.append(
                f"línea {p['estado_line']}: {p['id']} ({p['name']}) tiene TODO cerrado "
                f"({p['done']} tareas) pero Estado no es COMPLETA → '{p['estado']}'")
        elif p["done"] > 0 and p["pend"] > 0 and not (completa or en_curso):
            errors.append(
                f"línea {p['estado_line']}: {p['id']} ({p['name']}) tiene avance parcial "
                f"({p['done']}✓/{p['pend']}○) pero Estado dice '{p['estado']}' → debería ser EN CURSO")
    return errors


def lint(path: Path = ESTADO) -> list[str]:
    errors: list[str] = []
    lines = path.read_text().splitlines()

    current_sub: str | None = None
    sub_line: int = 0
    sub_kind: str | None = None   # "pendiente" | "completado" | None

    for i, line in enumerate(lines, 1):
        if _SECTION_HEADER.match(line):
            current_sub = None
            sub_kind = None
            continue

        m = _SUB_HEADER.match(line)
        if m:
            label = m.group(1).strip()
            if _PENDIENTE_RE.search(label):
                current_sub = label
                sub_line = i
                sub_kind = "pendiente"
            elif _COMPLETADO_RE.search(label):
                current_sub = label
                sub_line = i
                sub_kind = "completado"
            else:
                current_sub = None
                sub_kind = None
            continue

        if sub_kind == "pendiente" and _TASK_DONE.match(line):
            errors.append(
                f"línea {i}: tarea [x] bajo '#### {current_sub}' "
                f"(header en línea {sub_line}) — mover o eliminar el header"
            )
        elif sub_kind == "completado" and _TASK_OPEN.match(line):
            errors.append(
                f"línea {i}: tarea [ ] bajo '#### {current_sub}' "
                f"(header en línea {sub_line}) — mover o eliminar el header"
            )

    return errors


def main() -> None:
    lines = ESTADO.read_text().splitlines()
    errors = lint() + lint_phase_status(lines)

    if not errors:
        print("✓ estado.md sin inconsistencias (sub-headers + Estado de fase)")
        return

    print(f"✗ {len(errors)} problema(s) en estado.md:\n")
    for e in errors:
        print(f"  • {e}")
    print(
        "\nSolución: eliminar los headers '#### Pendiente' / '#### Completado' "
        "y ordenar las tareas directamente con [x]/[ ]."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Detecta inconsistencias en masterplan/estado.md:

  1. Tareas [x] bajo un header "#### Pendiente" (o similar)
  2. Tareas [ ] bajo un header "#### Completado" (o similar)

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
    errors = lint()

    if not errors:
        print("✓ estado.md sin inconsistencias Completado/Pendiente")
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

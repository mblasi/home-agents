#!/usr/bin/env python3
"""
Gestión del backlog — mantiene estado.md, issues.yaml y GitHub Issues en sync.

Uso:
  python scripts/backlog.py show [--pending | --done] [--phase N]
  python scripts/backlog.py add <task_id> <title> [--body TEXT] [--repo OWNER/REPO]
  python scripts/backlog.py done <task_id> [--no-sync]
  python scripts/backlog.py sync [--dry-run]
"""
import re
import sys
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
ESTADO = ROOT / "masterplan" / "estado.md"
ISSUES_YAML = ROOT / "masterplan" / "issues.yaml"
SYNC = ROOT / "scripts" / "sync_issues.py"
LINT = ROOT / "scripts" / "lint_estado.py"
DEFAULT_REPO = "mblasi/home-agents"

TASK_RE = re.compile(r"^-\s+\[([ x])\]\s+(\d+(?:\.\d+)+)\s+(.*)", re.IGNORECASE)
PHASE_RE = re.compile(r"^###\s+FASE\s+(\S+)")


# ── parsers ──────────────────────────────────────────────────────────────────

def parse_estado():
    """Returns list of dicts: line (1-indexed), done, id, desc, phase."""
    tasks = []
    current_phase = None
    for i, line in enumerate(ESTADO.read_text().splitlines(), 1):
        m = PHASE_RE.match(line)
        if m:
            current_phase = m.group(1).rstrip("-").strip()
            continue
        m = TASK_RE.match(line)
        if m:
            tasks.append({
                "line": i,
                "done": m.group(1).lower() == "x",
                "id": m.group(2),
                "desc": m.group(3).strip(),
                "phase": current_phase,
            })
    return tasks


def load_issue_map():
    """Returns {task_id: (number, repo)}."""
    import yaml
    raw = yaml.safe_load(ISSUES_YAML.read_text()) or {}
    result = {}
    for k, v in raw.items():
        if isinstance(v, int):
            result[str(k)] = (v, DEFAULT_REPO)
        elif isinstance(v, dict):
            result[str(k)] = (v["number"], v.get("repo", DEFAULT_REPO))
    return result


def phase_of(task_id: str) -> str:
    """'6.22' → '6', '2.5.1' → '2.5', '9.23' → '9'."""
    parts = task_id.rsplit(".", 1)
    return parts[0] if len(parts) > 1 else task_id


# ── show ─────────────────────────────────────────────────────────────────────

def cmd_show(args):
    filter_phase = None
    show_pending = True
    show_done = True
    i = 0
    while i < len(args):
        if args[i] == "--phase" and i + 1 < len(args):
            filter_phase = args[i + 1]; i += 2
        elif args[i] == "--pending":
            show_done = False; i += 1
        elif args[i] == "--done":
            show_pending = False; i += 1
        else:
            i += 1

    tasks = parse_estado()
    issue_map = load_issue_map()

    by_phase = defaultdict(list)
    phase_order = []
    seen = set()
    for t in tasks:
        if not show_pending and not t["done"]:
            continue
        if not show_done and t["done"]:
            continue
        if filter_phase and t["phase"] != filter_phase:
            continue
        if t["phase"] not in seen:
            phase_order.append(t["phase"])
            seen.add(t["phase"])
        by_phase[t["phase"]].append(t)

    if not phase_order:
        print("(sin tareas que mostrar)")
        return

    for phase in phase_order:
        task_list = by_phase[phase]
        total = len(task_list)
        done_count = sum(1 for t in task_list if t["done"])
        print(f"\n\033[1mFASE {phase}\033[0m  \033[2m{done_count}/{total}\033[0m")
        for t in task_list:
            mark = "\033[32m✓\033[0m" if t["done"] else "\033[33m·\033[0m"
            info = issue_map.get(t["id"])
            if info:
                num, repo = info
                tag = f" [{repo.split('/')[1]}]" if repo != DEFAULT_REPO else ""
                issue_str = f"#{num}{tag}"
            else:
                issue_str = "(sin issue)"
            tid = t["id"].ljust(8)
            iss = issue_str.ljust(12)
            desc = t["desc"][:70]
            print(f"  {mark} {tid}  \033[2m{iss}\033[0m  {desc}")
    print()


# ── add ──────────────────────────────────────────────────────────────────────

def cmd_add(args):
    if len(args) < 2:
        sys.exit("Uso: backlog.py add <task_id> <title> [--body TEXT] [--repo OWNER/REPO]")

    task_id = args[0]
    title = args[1]
    body = f"Tarea {task_id} del masterplan — ver `masterplan/estado.md`."
    repo = DEFAULT_REPO

    i = 2
    while i < len(args):
        if args[i] == "--body" and i + 1 < len(args):
            body = args[i + 1]; i += 2
        elif args[i] == "--repo" and i + 1 < len(args):
            repo = args[i + 1]; i += 2
        else:
            i += 1

    tasks = parse_estado()
    if any(t["id"] == task_id for t in tasks):
        sys.exit(f"Error: {task_id} ya existe en estado.md")

    phase = phase_of(task_id)

    # Find insertion point: after last task of same phase
    insert_after = None  # 0-indexed
    for t in tasks:
        if t["phase"] == phase:
            insert_after = t["line"] - 1

    if insert_after is None:
        sys.exit(f"Error: no se encontró FASE {phase} en estado.md — agregar el header manualmente primero")

    # Create GH issue
    print(f"Creando issue en {repo}…")
    result = subprocess.run(
        ["gh", "issue", "create", "--repo", repo,
         "--title", f"[{task_id}] {title}",
         "--body", body],
        capture_output=True, text=True, check=True,
    )
    url = result.stdout.strip()
    issue_num = int(url.rstrip("/").split("/")[-1])
    print(f"Issue #{issue_num}: {url}")

    # Insert into estado.md. insert_after is the FIRST line of the last task of the
    # phase; tasks can span multiple (indented) continuation lines, so extend past
    # them to avoid splitting the task in two.
    lines = ESTADO.read_text().splitlines(keepends=True)
    insert_after = _task_last_line(lines, insert_after)
    new_task_line = f"- [ ] {task_id}  {title}\n"
    lines.insert(insert_after + 1, new_task_line)
    ESTADO.write_text("".join(lines))
    print(f"Insertado en estado.md después de línea {insert_after + 1}")


def _task_last_line(lines, start_idx):
    """Given the 0-indexed first line of a task, return the 0-indexed last line,
    extending over indented continuation lines (description that wraps). Stops at the
    first blank line, new task, phase/section header, or any non-indented line."""
    end = start_idx
    for k in range(start_idx + 1, len(lines)):
        line = lines[k]
        if not line.strip():
            break
        if line[0] not in (" ", "\t"):
            break
        end = k
    return end

    # Append to issues.yaml
    _append_to_issues_yaml(task_id, issue_num, repo, phase)
    print(f"Registrado en issues.yaml")


def _append_to_issues_yaml(task_id: str, issue_num: int, repo: str, phase: str):
    yaml_lines = ISSUES_YAML.read_text().splitlines(keepends=True)

    if repo == DEFAULT_REPO:
        new_entry = f'"{task_id}": {issue_num}\n'
    else:
        new_entry = f'"{task_id}": {{number: {issue_num}, repo: {repo}}}\n'

    # Find the section comment for this phase
    section_pat = re.compile(r"#\s*──\s*FASE\s+" + re.escape(phase) + r"\b")
    section_start = None
    for j, yl in enumerate(yaml_lines):
        if section_pat.search(yl):
            section_start = j
            break

    if section_start is not None:
        # Find end of section (next # ── block or EOF)
        section_end = len(yaml_lines)
        for j in range(section_start + 1, len(yaml_lines)):
            if re.match(r"^# ──", yaml_lines[j]):
                section_end = j
                break
        # Last non-empty, non-comment line in section
        last_entry = section_start
        for j in range(section_start, section_end):
            if yaml_lines[j].strip() and not yaml_lines[j].strip().startswith("#"):
                last_entry = j
        yaml_lines.insert(last_entry + 1, new_entry)
    else:
        # No existing section — insert before Anexos or at end
        header = f'\n# ── FASE {phase} ─────────────────────────────────────────────────────────────\n'
        anexos_idx = next(
            (j for j, yl in enumerate(yaml_lines) if re.match(r"^# ── Anexos", yl)),
            None,
        )
        if anexos_idx is not None:
            yaml_lines.insert(anexos_idx, new_entry)
            yaml_lines.insert(anexos_idx, header)
        else:
            yaml_lines.append(header)
            yaml_lines.append(new_entry)

    ISSUES_YAML.write_text("".join(yaml_lines))


# ── done ─────────────────────────────────────────────────────────────────────

def cmd_done(args):
    if not args:
        sys.exit("Uso: backlog.py done <task_id> [--no-sync]")

    task_id = args[0]
    no_sync = "--no-sync" in args

    lines = ESTADO.read_text().splitlines(keepends=True)
    found = False
    for i, line in enumerate(lines):
        m = TASK_RE.match(line)
        if m and m.group(2) == task_id:
            if m.group(1).lower() == "x":
                print(f"{task_id} ya está marcada [x]")
                return
            lines[i] = line.replace("[ ]", "[x]", 1)
            found = True
            break

    if not found:
        sys.exit(f"Error: {task_id} no encontrado en estado.md")

    ESTADO.write_text("".join(lines))
    print(f"✓ {task_id} marcada como completada en estado.md")

    result = subprocess.run([sys.executable, str(LINT)])
    if result.returncode != 0:
        sys.exit("Lint falló — corregir antes de continuar")

    if not no_sync:
        subprocess.run([sys.executable, str(SYNC)], check=True)


# ── sync ─────────────────────────────────────────────────────────────────────

def cmd_sync(args):
    result = subprocess.run([sys.executable, str(LINT)])
    if result.returncode != 0:
        sys.exit("Lint falló — corregir antes de sincronizar")
    subprocess.run([sys.executable, str(SYNC)] + args, check=True)


# ── main ─────────────────────────────────────────────────────────────────────

COMMANDS = {
    "show": cmd_show,
    "add": cmd_add,
    "done": cmd_done,
    "sync": cmd_sync,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()

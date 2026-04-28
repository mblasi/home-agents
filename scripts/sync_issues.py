#!/usr/bin/env python3
"""
Sincroniza el estado de masterplan/estado.md con los issues de GitHub.

  - [x] → cierra el issue correspondiente
  - [ ] → reabre el issue si estaba cerrado

Uso:
  python scripts/sync_issues.py           # aplica cambios
  python scripts/sync_issues.py --dry-run # solo muestra qué haría
"""
import re
import sys
import json
import subprocess
from pathlib import Path

REPO = "mblasi/home-agents"
ROOT = Path(__file__).parent.parent
ESTADO = ROOT / "masterplan" / "estado.md"
MAPPING = ROOT / "masterplan" / "issues.yaml"

TASK_RE = re.compile(r"-\s\[([ x])\]\s+(\d+(?:\.\d+)+)")


def parse_tasks():
    tasks = {}
    for line in ESTADO.read_text().splitlines():
        m = TASK_RE.search(line)
        if m:
            tasks[m.group(2)] = m.group(1) == "x"
    return tasks


def fetch_issue_states():
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "all",
         "--json", "number,state", "--limit", "300"],
        capture_output=True, text=True, check=True,
    )
    return {str(i["number"]): i["state"] for i in json.loads(result.stdout)}


def load_mapping():
    import yaml
    return {str(k): int(v) for k, v in yaml.safe_load(MAPPING.read_text()).items()}


def gh(cmd, dry_run):
    print("   $", " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, check=True)


def main():
    dry_run = "--dry-run" in sys.argv

    try:
        mapping = load_mapping()
    except Exception as e:
        sys.exit(f"Error leyendo {MAPPING}: {e}")

    tasks = parse_tasks()
    states = fetch_issue_states()

    changed = 0
    for task_id, issue_num in sorted(mapping.items(), key=lambda x: x[1]):
        done = tasks.get(task_id)
        if done is None:
            print(f"[WARN] {task_id} no encontrado en estado.md")
            continue

        issue_str = str(issue_num)
        state = states.get(issue_str, "UNKNOWN").upper()
        is_open = state == "OPEN"

        if done and is_open:
            print(f"[{task_id}] #{issue_num}: completado → cerrando")
            gh(["gh", "issue", "close", issue_str, "--repo", REPO], dry_run)
            changed += 1
        elif not done and not is_open:
            print(f"[{task_id}] #{issue_num}: pendiente → reabriendo")
            gh(["gh", "issue", "reopen", issue_str, "--repo", REPO], dry_run)
            changed += 1
        else:
            status = "✓ cerrado" if not is_open else "✓ abierto"
            print(f"[{task_id}] #{issue_num}: ok ({status})")

    suffix = " (dry-run)" if dry_run else ""
    print(f"\n{changed} issue(s) actualizados{suffix}.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Sincroniza el estado de masterplan/estado.md con los issues de GitHub.

  - [x] → cierra el issue correspondiente
  - [ ] → reabre el issue si estaba cerrado

Soporta issues en múltiples repos. El repo por defecto es mblasi/home-agents.
Issues en submodules usan formato dict en issues.yaml:
  "2.1": {number: 1, repo: mblasi/home-agents-core}

Uso:
  python scripts/sync_issues.py           # aplica cambios
  python scripts/sync_issues.py --dry-run # solo muestra qué haría
"""
import re
import sys
import json
import subprocess
from collections import defaultdict
from pathlib import Path

DEFAULT_REPO = "mblasi/home-agents"
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


def load_mapping():
    import yaml
    raw = yaml.safe_load(MAPPING.read_text())
    result = {}
    for k, v in raw.items():
        if isinstance(v, int):
            result[str(k)] = {"number": v, "repo": DEFAULT_REPO}
        elif isinstance(v, dict):
            result[str(k)] = {"number": v["number"], "repo": v.get("repo", DEFAULT_REPO)}
        else:
            raise ValueError(f"Formato inválido para {k}: {v!r}")
    return result


def fetch_issue_states(repo):
    result = subprocess.run(
        ["gh", "issue", "list", "--repo", repo, "--state", "all",
         "--json", "number,state", "--limit", "300"],
        capture_output=True, text=True, check=True,
    )
    return {str(i["number"]): i["state"] for i in json.loads(result.stdout)}


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

    # Agrupar por repo para minimizar llamadas a la API
    repos_needed = {entry["repo"] for entry in mapping.values()}
    states_by_repo = {}
    skipped_repos = set()
    for repo in repos_needed:
        try:
            states_by_repo[repo] = fetch_issue_states(repo)
        except subprocess.CalledProcessError as e:
            print(f"[SKIP] {repo}: sin acceso ({e.returncode}) — issues de este repo omitidos")
            skipped_repos.add(repo)

    changed = 0
    for task_id, entry in sorted(mapping.items(), key=lambda x: x[1]["number"]):
        repo = entry["repo"]
        issue_num = entry["number"]
        done = tasks.get(task_id)

        if repo in skipped_repos:
            continue

        if done is None:
            print(f"[WARN] {task_id} no encontrado en estado.md")
            continue

        issue_str = str(issue_num)
        state = states_by_repo[repo].get(issue_str, "UNKNOWN").upper()
        is_open = state == "OPEN"

        repo_label = "" if repo == DEFAULT_REPO else f" [{repo.split('/')[1]}]"

        if done and is_open:
            print(f"[{task_id}]{repo_label} #{issue_num}: completado → cerrando")
            gh(["gh", "issue", "close", issue_str, "--repo", repo], dry_run)
            changed += 1
        elif not done and not is_open:
            print(f"[{task_id}]{repo_label} #{issue_num}: pendiente → reabriendo")
            gh(["gh", "issue", "reopen", issue_str, "--repo", repo], dry_run)
            changed += 1
        else:
            status = "✓ cerrado" if not is_open else "✓ abierto"
            print(f"[{task_id}]{repo_label} #{issue_num}: ok ({status})")

    suffix = " (dry-run)" if dry_run else ""
    print(f"\n{changed} issue(s) actualizados{suffix}.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Migración de los JSON de ~/.local/share/capitan/ (+ panels.yaml) a SQLite (FASE 32.3).

Idempotente (upsert) y con --dry-run (reporta qué insertaría sin escribir).
No borra los JSON — eso es 32.6, una vez validada la migración.

Uso:
    python scripts/migrate_to_db.py --dry-run
    python scripts/migrate_to_db.py
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
import db as _db  # noqa: E402

DATA_DIR = Path(os.environ.get("CAPITAN_DATA", str(Path.home() / ".local/share/capitan")))
REPO = Path(__file__).parent.parent

# Campos JSON de users que se serializan como texto
_USER_JSON_FIELDS = ("preferences", "agent_ids", "revoked_agents", "documents")
_USER_COLS = ("id", "name", "role", "relationship", "wa_phone", "has_embedding",
              "onboarding_step", "onboarding_complete", "gcal_email", "gcal_app_password",
              "preferences", "agent_ids", "revoked_agents", "documents", "created_at")


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


class Migrator:
    def __init__(self, dry_run: bool):
        self.dry = dry_run
        self.counts: dict[str, int] = {}

    def _bump(self, kind: str, n: int = 1):
        self.counts[kind] = self.counts.get(kind, 0) + n

    def _upsert(self, table: str, row: dict, pk: str):
        self._bump(table)
        if not self.dry:
            _db.upsert(table, row, pk)

    def _doc(self, kind: str, key: str, data):
        self._bump(f"doc:{kind}")
        if not self.dry:
            _db.doc_set(kind, key, data)

    # ── Entidades normalizadas ────────────────────────────────────────────────

    def users(self):
        d = _load(DATA_DIR / "users.json") or {}
        for uid, u in d.items():
            row = {c: u.get(c) for c in _USER_COLS}
            row["id"] = uid
            for f in _USER_JSON_FIELDS:
                if row.get(f) is not None and not isinstance(row[f], str):
                    row[f] = json.dumps(row[f], ensure_ascii=False)
            for b in ("has_embedding", "onboarding_complete"):
                if isinstance(row.get(b), bool):
                    row[b] = int(row[b])
            self._upsert("users", {k: v for k, v in row.items() if v is not None}, "id")

    def panels(self):
        try:
            import yaml
        except ImportError:
            return
        p = REPO / "panels.yaml"
        if not p.is_file():
            return
        for panel in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("panels", []):
            row = {k: panel.get(k) for k in ("name", "room", "ip", "mac", "node_id", "ha_user")}
            row["users"] = json.dumps(panel.get("users", []), ensure_ascii=False)
            self._upsert("panels", {k: v for k, v in row.items() if v is not None}, "name")

    def per_user_docs(self):
        # intents/goals/routines/plan_events: un archivo por usuario (<user>.json)
        for subdir in ("intents", "goals", "routines", "plan_events"):
            for f in glob.glob(str(DATA_DIR / subdir / "*.json")):
                self._doc(subdir, Path(f).stem, _load(Path(f)))
        # tools: un archivo por agente (<agent>.json)
        for f in glob.glob(str(DATA_DIR / "tools" / "*.json")):
            self._doc("tools", Path(f).stem, _load(Path(f)))
        # user_context: subdir por usuario, un archivo por agente → key "<user>/<agent>"
        for f in glob.glob(str(DATA_DIR / "user_context" / "*" / "*.json")):
            p = Path(f)
            self._doc("user_context", f"{p.parent.name}/{p.stem}", _load(p))

    # ── Document store (lo append-heavy / menos estructurado) ─────────────────

    def documents(self):
        # archivos flat → documents. fixed_key: None=dict {key:obj} | "@campo"=lista
        # keyeada por item[campo] | str=clave fija para el archivo entero.
        flat = {
            "conversations.json":        ("conversation", "@id"),  # lista de {id, ...}
            "agents.json":               ("agent_config", None),   # dict {agent_id: {...}}
            "finance_news_index.json":   ("finance_news", "index"),
            "finance_templates.json":    ("misc", "finance_templates"),
            "feriados.json":             ("misc", "feriados"),
            "feriados_sync.json":        ("misc", "feriados_sync"),
            "routine_last_detect.json":  ("misc", "routine_last_detect"),
        }
        for fname, (kind, fixed_key) in flat.items():
            data = _load(DATA_DIR / fname)
            if data is None:
                continue
            if fixed_key and fixed_key.startswith("@"):
                field = fixed_key[1:]
                for item in (data if isinstance(data, list) else []):
                    self._doc(kind, str(item.get(field, "")), item)
            elif fixed_key:
                self._doc(kind, fixed_key, data)
            elif isinstance(data, dict):
                for k, v in data.items():
                    self._doc(kind, k, v)

        # patrones por-usuario → documents. (prefijo, kind) → key sin prefijo.
        # portfolio_matias → portfolio/matias ; history_haos_matias → history/haos_matias ;
        # ml_token_matias → token/ml_matias ; mp_token_matias → token/mp_matias
        patterns = [
            ("portfolio_",          "portfolio"),
            ("finance_templates_",  "finance_templates"),
            ("history_",            "history"),
            ("ml_token_",           "token"),
            ("mp_token_",           "token"),
        ]
        for prefix, kind in patterns:
            for f in glob.glob(str(DATA_DIR / f"{prefix}*.json")):
                stem = Path(f).stem
                key = stem[len(prefix):]
                if kind == "token":
                    key = prefix[:2] + "_" + key   # ml_/mp_ + user
                self._doc(kind, key, _load(Path(f)))
        # ml_prices.json (single)
        ml = _load(DATA_DIR / "ml_prices.json")
        if ml is not None:
            self._doc("misc", "ml_prices", ml)

    def run(self):
        for step in (self.users, self.panels, self.per_user_docs, self.documents):
            step()
        return self.counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="reporta sin escribir")
    args = ap.parse_args()
    if not args.dry_run:
        _db.get_db()  # crea la DB + esquema
    m = Migrator(args.dry_run)
    counts = m.run()
    print(("[dry-run] insertaría:" if args.dry_run else "[ok] migrado:"))
    for k in sorted(counts):
        print(f"  {k:24} {counts[k]}")
    print(f"  {'TOTAL':24} {sum(counts.values())}")
    print(f"DB: {_db.DB_PATH}" if not args.dry_run else "(dry-run, sin escribir)")


if __name__ == "__main__":
    main()

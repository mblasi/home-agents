"""FASE 43.5 — parsing de config del form del backoffice (incl. el orquestador).

El backoffice no tenía suite; este test cubre _parse_config_from_form, en particular el tipo
`bool` (checkbox) que el orquestador usa para routing_hint_enabled. Correr con:
    cd backoffice && python -m pytest tests/ -q
"""
import sys
from pathlib import Path

from starlette.datastructures import FormData

sys.path.insert(0, str(Path(__file__).parent.parent))
import server

SCHEMA = {
    "model":                {"type": "select"},
    "system_prompt":        {"type": "text"},
    "max_iters":            {"type": "int"},
    "llm_budget":           {"type": "int"},
    "routing_hint_enabled": {"type": "bool"},
}


def test_parses_select_int_text():
    f = FormData([("config_model", "qwen2.5:3b"), ("config_max_iters", "7"),
                  ("config_system_prompt", "SOS X.")])
    cfg = server._parse_config_from_form(f, SCHEMA)
    assert cfg["model"] == "qwen2.5:3b"
    assert cfg["max_iters"] == 7 and isinstance(cfg["max_iters"], int)
    assert cfg["system_prompt"] == "SOS X."


def test_bool_checked_true():
    f = FormData([("config_routing_hint_enabled", "1")])
    assert server._parse_config_from_form(f, SCHEMA)["routing_hint_enabled"] is True


def test_bool_unchecked_false():
    # el checkbox ausente debe quedar False (no omitido) — si no, nunca se podría desactivar
    f = FormData([("config_model", "x")])
    cfg = server._parse_config_from_form(f, SCHEMA)
    assert cfg["routing_hint_enabled"] is False


def test_absent_non_bool_keys_skipped():
    f = FormData([("config_routing_hint_enabled", "1")])
    cfg = server._parse_config_from_form(f, SCHEMA)
    assert "model" not in cfg and "max_iters" not in cfg  # no presentes → no se tocan


def test_bad_int_falls_back_to_str():
    f = FormData([("config_max_iters", "abc")])
    assert server._parse_config_from_form(f, SCHEMA)["max_iters"] == "abc"

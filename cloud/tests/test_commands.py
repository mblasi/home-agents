"""Tests del catálogo tipado de comandos (allow-list cerrada)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.commands import CommandError, catalog_summary, validate_command


def test_restart_ok():
    assert validate_command("service.restart", {"service": "capitan-core"}) == {
        "service": "capitan-core"
    }


def test_unknown_type_rejected():
    with pytest.raises(CommandError):
        validate_command("shell.exec", {"cmd": "rm -rf /"})


def test_unknown_param_rejected():
    with pytest.raises(CommandError):
        validate_command("service.restart", {"service": "capitan-core", "x": 1})


def test_bad_enum_rejected():
    with pytest.raises(CommandError):
        validate_command("service.restart", {"service": "nginx"})


def test_missing_required_rejected():
    with pytest.raises(CommandError):
        validate_command("service.restart", {})


def test_optional_param_omitted():
    assert validate_command("service.status", {}) == {}


def test_logs_lines_range():
    assert validate_command("logs.tail", {"service": "capitan-wa", "lines": 100})["lines"] == 100
    with pytest.raises(CommandError):
        validate_command("logs.tail", {"service": "capitan-wa", "lines": 0})
    with pytest.raises(CommandError):
        validate_command("logs.tail", {"service": "capitan-wa", "lines": 9999})


def test_bool_param_type_checked():
    assert validate_command("deploy.run", {"restart_wa": True}) == {"restart_wa": True}
    with pytest.raises(CommandError):
        validate_command("deploy.run", {"restart_wa": "yes"})


def test_no_params_command():
    assert validate_command("wakeword.retrain", {}) == {}


def test_catalog_summary_shape():
    cat = catalog_summary()
    types = {c["type"] for c in cat}
    assert "service.restart" in types and "voice.reenroll" in types

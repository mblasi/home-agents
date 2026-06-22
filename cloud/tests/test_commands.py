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


# ── deploy.release (FASE 34): refs por repo + lista de servicios ───────────────

def test_deploy_release_sin_params():
    assert validate_command("deploy.release", {}) == {}


def test_deploy_release_refs_validos():
    out = validate_command("deploy.release",
                           {"core_ref": "v1.2.3", "umbrella_ref": "abc1234", "ear_ref": "main"})
    assert out == {"core_ref": "v1.2.3", "umbrella_ref": "abc1234", "ear_ref": "main"}


def test_deploy_release_ref_con_inyeccion_rechazado():
    for bad in ("a; rm -rf /", "x && y", "$(whoami)", "a b", "v1`id`"):
        with pytest.raises(CommandError):
            validate_command("deploy.release", {"core_ref": bad})


def test_deploy_release_services_lista_valida():
    out = validate_command("deploy.release", {"services": ["core", "bridge"]})
    assert out == {"services": ["core", "bridge"]}


def test_deploy_release_services_invalidos():
    with pytest.raises(CommandError):
        validate_command("deploy.release", {"services": ["core", "nope"]})
    with pytest.raises(CommandError):
        validate_command("deploy.release", {"services": "core"})   # no es lista
    with pytest.raises(CommandError):
        validate_command("deploy.release", {"services": []})       # vacía


def test_deploy_release_param_desconocido_rechazado():
    with pytest.raises(CommandError):
        validate_command("deploy.release", {"wa_ref": "x"})


# ── deploy.cloud (T4): targets de Cloud Run ───────────────────────────────────

def test_deploy_cloud_sin_params():
    assert validate_command("deploy.cloud", {}) == {}


def test_deploy_cloud_services_validos():
    assert validate_command("deploy.cloud", {"services": ["cloud-bo"]}) == {"services": ["cloud-bo"]}


def test_deploy_cloud_target_invalido():
    with pytest.raises(CommandError):
        validate_command("deploy.cloud", {"services": ["core"]})   # core no es target cloudrun


# ── deploy.satellites (34.16): force pull de paneles ──────────────────────────

def test_deploy_satellites_sin_params():
    assert validate_command("deploy.satellites", {}) == {}


def test_deploy_satellites_node_id():
    assert validate_command("deploy.satellites", {"node_id": "comedor"}) == {"node_id": "comedor"}
    assert validate_command("deploy.satellites", {"node_id": "*"}) == {"node_id": "*"}


def test_deploy_satellites_param_desconocido():
    with pytest.raises(CommandError):
        validate_command("deploy.satellites", {"nodo": "comedor"})


# ── FASE 37.2: comandos de operación acotados ─────────────────────────────────

def test_agent_toggle_ok():
    assert validate_command("agent.toggle", {"agent_id": "haos", "status": "planned"}) == {
        "agent_id": "haos", "status": "planned"}


def test_agent_toggle_status_invalido():
    with pytest.raises(CommandError):
        validate_command("agent.toggle", {"agent_id": "haos", "status": "on"})


def test_agent_toggle_requiere_agent_y_status():
    with pytest.raises(CommandError):
        validate_command("agent.toggle", {"agent_id": "haos"})
    with pytest.raises(CommandError):
        validate_command("agent.toggle", {"status": "active"})


def test_panel_reboot_ok():
    assert validate_command("panel.reboot", {"node_id": "comedor"}) == {"node_id": "comedor"}
    with pytest.raises(CommandError):
        validate_command("panel.reboot", {})


def test_proactive_run_ok():
    assert validate_command("proactive.run", {"agent_id": "clima"}) == {"agent_id": "clima"}
    with pytest.raises(CommandError):
        validate_command("proactive.run", {})


def test_new_commands_in_catalog_summary():
    types = {c["type"] for c in catalog_summary()}
    assert {"agent.toggle", "panel.reboot", "proactive.run"} <= types


# ── FASE 37.6: metadata de presentación en el catálogo ────────────────────────

def _cmd(t):
    return next(c for c in catalog_summary() if c["type"] == t)


def _param(t, name):
    return next(p for p in _cmd(t)["params"] if p["name"] == name)


def test_catalog_has_command_label():
    assert _cmd("service.restart")["label"] == "Reiniciar servicio"
    # comando sin label declarado cae al type
    assert all("label" in c for c in catalog_summary())


def test_enum_param_exposes_choices():
    p = _param("service.restart", "service")
    assert p["kind"] == "enum"
    assert "capitan-core" in p["choices"] and isinstance(p["choices"], list)


def test_int_param_exposes_min_max_default():
    p = _param("logs.tail", "lines")
    assert p["kind"] == "int" and p["min"] == 1 and p["max"] == 500 and p["default"] == 100


def test_bool_param_kind():
    assert _param("deploy.run", "restart_wa")["kind"] == "bool"


def test_multi_param_kind():
    p = _param("deploy.release", "services")
    assert p["kind"] == "multi" and "core" in p["choices"]


def test_entity_param_kinds():
    assert _param("agent.toggle", "agent_id")["kind"] == "agent"
    assert _param("panel.reboot", "node_id")["kind"] == "node"
    assert _param("voice.reenroll", "user_id")["kind"] == "user"


def test_param_without_presentation_defaults_to_str():
    p = _param("deploy.release", "core_ref")
    assert p["kind"] == "str" and "label" in p


def test_presentation_does_not_alter_validation():
    # el catálogo enriquecido no cambia validate_command: choices presentacionales == enum real
    assert validate_command("agent.toggle", {"agent_id": "haos", "status": "active"})["status"] == "active"
    with pytest.raises(CommandError):
        validate_command("logs.tail", {"service": "capitan-core", "lines": 999})

"""Tests del invocador local por target (deploy_cli): resuelve el target al MISMO comando
tipado que el cloud-bo y lo valida con el contrato. No ejecuta deploy real."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import deploy_cli as dc  # noqa: E402
from app.commands import validate_command  # noqa: E402


def test_sin_target_es_release_default():
    assert dc.resolve_target(None, None) == ("deploy.release", {})


def test_services_del_brain():
    assert dc.resolve_target("core", None) == ("deploy.release", {"services": ["core"]})
    # audio_server es el target, el repo/service subyacente es ear
    assert dc.resolve_target("audio_server", None) == ("deploy.release", {"services": ["ear"]})
    assert dc.resolve_target("backoffice", None) == ("deploy.release", {"services": ["backoffice"]})


def test_cloud_bo():
    assert dc.resolve_target("cloud-bo", None) == ("deploy.cloud", {"services": ["cloud-bo"]})


def test_paneles():
    assert dc.resolve_target("panels", None) == ("deploy.satellites", {"node_id": "*"})
    assert dc.resolve_target("nspanel-comedor", None) == ("deploy.satellites", {"node_id": "nspanel-comedor"})
    assert dc.resolve_target("panel:nspanel-pieza", None) == ("deploy.satellites", {"node_id": "nspanel-pieza"})


def test_ref_solo_para_release():
    _, params = dc.resolve_target("core", {"core_ref": "v0.1.0"})
    assert params == {"services": ["core"], "core_ref": "v0.1.0"}


def test_typo_no_es_no_op_silencioso():
    # un nombre que no es target ni node_id plausible → error explícito (no un deploy vacío)
    with pytest.raises(ValueError):
        dc.resolve_target("backofice", None)   # typo


def test_targets_resueltos_pasan_el_contrato():
    # cada target estático resuelve a params que el catálogo TIPADO acepta (mismo gate que la nube)
    for name in ("core", "audio_server", "backoffice", "wa", "bridge", "cloud-bo", "panels"):
        cmd, params = dc.resolve_target(name, None)
        validate_command(cmd, params)   # no lanza

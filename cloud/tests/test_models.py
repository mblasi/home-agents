"""Tests del contrato del snapshot (regresión del bug de schema_version)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.models import SCHEMA_VERSION, StateSnapshot


def test_schema_version_constant_matches_default():
    # ingest_state compara contra SCHEMA_VERSION, no instancia StateSnapshot() vacío
    # (que falla porque ts/host son requeridos). Regresión del 500 en /ingest/state.
    snap = StateSnapshot(ts="2026-06-16T00:00:00Z", host="x")
    assert snap.schema_version == SCHEMA_VERSION


def test_minimal_snapshot_validates():
    snap = StateSnapshot(ts="2026-06-16T00:00:00Z", host="capitan-lxc")
    d = snap.model_dump()
    assert d["schema_version"] == 1
    assert d["services"] == {} and d["agents"] == []


def test_ts_and_host_required():
    with pytest.raises(Exception):
        StateSnapshot()

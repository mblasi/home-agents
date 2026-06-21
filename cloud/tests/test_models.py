"""Tests del contrato del snapshot (regresión del bug de schema_version)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.models import SCHEMA_VERSION, Counts, StateSnapshot, Wakeword


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


# ── FASE 37.1: campos ampliados (alerts, wakeword.status, counts) ──

def test_new_fields_default_empty():
    snap = StateSnapshot(ts="2026-06-21T00:00:00Z", host="capitan-lxc")
    d = snap.model_dump()
    assert d["alerts"] == []
    assert d["counts"] == {"intents": 0, "goals": 0, "routines": 0, "conversations": 0}
    assert d["wakeword"]["status"] == "idle"


def test_counts_are_only_aggregates():
    # El contrato sólo admite enteros: imposible filtrar contenido PID por este campo.
    c = Counts(intents=3, goals=1, routines=2, conversations=7)
    assert c.model_dump() == {"intents": 3, "goals": 1, "routines": 2, "conversations": 7}
    with pytest.raises(Exception):
        Counts(intents=[{"text": "secreto"}])  # listas/objetos rechazados


def test_alerts_and_wakeword_status_roundtrip():
    snap = StateSnapshot(
        ts="2026-06-21T00:00:00Z", host="capitan-lxc",
        alerts=["El documento de X vence en 3 días"],
        wakeword=Wakeword(status="running"),
        counts=Counts(conversations=5),
    )
    d = snap.model_dump()
    assert d["alerts"] == ["El documento de X vence en 3 días"]
    assert d["wakeword"]["status"] == "running"
    assert d["counts"]["conversations"] == 5

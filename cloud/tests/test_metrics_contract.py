"""Tests del contrato de métricas (FASE 35.5) y su RBAC (35.6)."""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bridge"))
from app import rbac
from app.models import METRICS_SCHEMA_VERSION, MetricsSnapshot


def test_minimal_metrics_snapshot_validates():
    snap = MetricsSnapshot(ts="2026-06-18T00:00:00Z")
    d = snap.model_dump()
    assert d["schema_version"] == METRICS_SCHEMA_VERSION
    assert d["window_hours"] == 24
    assert d["voice_summary"] == {} and d["llm_by_model"] == []
    assert d["voice_conf_series"] == {}   # FASE 37.12


def test_metrics_snapshot_carries_voice_conf_series():
    snap = MetricsSnapshot(ts="2026-06-21T00:00:00Z", voice_conf_series={
        "labels": [1, 2], "series": [{"name": "known_conf", "data": [0.8, 0.85]},
                                      {"name": "threshold", "data": [0.6, 0.6]}]})
    assert snap.voice_conf_series["series"][0]["name"] == "known_conf"


def test_ts_required():
    with pytest.raises(Exception):
        MetricsSnapshot()


def test_filter_metrics_full_keeps_detail():
    m = {"voice_summary": {"total": 1}, "llm_by_model": [{"model": "x"}],
         "llm_by_agent": [{"agent_id": "haos"}], "retrains": [{"version": "v1"}]}
    out = rbac.filter_metrics(m, rbac.caps_for("admin"))
    assert out["llm_by_model"] and out["llm_by_agent"] and out["retrains"]


def test_filter_metrics_basic_strips_detail():
    m = {"voice_summary": {"total": 1}, "voice_series": {"labels": [1]},
         "llm_summary": {"requests": {"requests": 2}},
         "llm_by_model": [{"model": "x"}], "llm_by_agent": [{"agent_id": "haos"}],
         "retrains": [{"version": "v1"}]}
    out = rbac.filter_metrics(m, rbac.caps_for("adolescente"))
    assert out["llm_by_model"] == [] and out["llm_by_agent"] == [] and out["retrains"] == []
    # los resúmenes y series sí se conservan
    assert out["voice_summary"] == {"total": 1} and out["voice_series"] == {"labels": [1]}
    assert out["llm_summary"] == {"requests": {"requests": 2}}


# ── Contrato bridge → nube (35.7): el snapshot del bridge valida como MetricsSnapshot ──

def test_bridge_snapshot_validates_against_cloud_model():
    import metrics_snapshot

    def fake_get(url, **k):
        if "by-model" in url: return {"models": [{"model": "qwen2.5:7b", "calls": 3}]}
        if "by-agent" in url: return {"agents": [{"agent_id": "haos", "steps": 2}]}
        if "retrains" in url: return {"retrains": [{"version": "v1"}]}
        if "summary" in url:  return {"total": 5, "tp": 4, "fp": 1}
        return {"labels": [1, 2], "series": [{"name": "tp", "data": [1, 1]}]}

    with patch.object(metrics_snapshot, "_get", fake_get):
        snap = metrics_snapshot.build_metrics_snapshot()
    # No debe lanzar: el shape del bridge es aceptado por el contrato de la nube.
    model = MetricsSnapshot(**snap)
    assert model.schema_version == METRICS_SCHEMA_VERSION
    assert model.llm_by_model[0]["model"] == "qwen2.5:7b"
    assert model.voice_summary["total"] == 5


def test_empty_bridge_snapshot_validates():
    import metrics_snapshot
    with patch.object(metrics_snapshot, "_get", lambda *a, **k: None):
        snap = metrics_snapshot.build_metrics_snapshot()
    MetricsSnapshot(**snap)  # no lanza

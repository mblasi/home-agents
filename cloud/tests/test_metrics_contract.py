"""Tests del contrato de métricas (FASE 35.5) y su RBAC (35.6)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import rbac
from app.models import METRICS_SCHEMA_VERSION, MetricsSnapshot


def test_minimal_metrics_snapshot_validates():
    snap = MetricsSnapshot(ts="2026-06-18T00:00:00Z")
    d = snap.model_dump()
    assert d["schema_version"] == METRICS_SCHEMA_VERSION
    assert d["window_hours"] == 24
    assert d["voice_summary"] == {} and d["llm_by_model"] == []


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

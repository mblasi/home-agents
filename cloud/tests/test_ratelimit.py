"""Tests del token bucket (rate limiting)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.ratelimit import TokenBucket


def test_allows_within_burst():
    tb = TokenBucket(rate_per_min=60, burst=5)
    assert all(tb.check("k") for _ in range(5))


def test_blocks_over_burst():
    tb = TokenBucket(rate_per_min=60, burst=3)
    assert tb.check("k") and tb.check("k") and tb.check("k")
    assert not tb.check("k")


def test_per_key_isolation():
    tb = TokenBucket(rate_per_min=60, burst=1)
    assert tb.check("a")
    assert not tb.check("a")
    assert tb.check("b")  # otra identidad, su propio bucket


def test_refill_over_time(monkeypatch):
    import app.ratelimit as rl
    t = {"v": 1000.0}
    monkeypatch.setattr(rl.time, "monotonic", lambda: t["v"])
    tb = TokenBucket(rate_per_min=60, burst=1)  # 1 token/seg
    assert tb.check("k")
    assert not tb.check("k")
    t["v"] += 1.1  # pasa >1s → se recarga 1 token
    assert tb.check("k")

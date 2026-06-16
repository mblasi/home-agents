"""Rate limiting in-memory (token bucket) por identidad. FASE 33 (33.14).

Por instancia de Cloud Run (scale-to-zero, máx 2): suficiente para un backoffice de
un solo usuario + un bridge. No necesita backend distribuido. Protege de loops
descontrolados del bridge o abuso desde una credencial comprometida.
"""
from __future__ import annotations

import threading
import time

from fastapi import HTTPException


class TokenBucket:
    def __init__(self, rate_per_min: int, burst: int | None = None):
        self.capacity = burst or rate_per_min
        self.refill_per_sec = rate_per_min / 60.0
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_ts)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
            if tokens < 1:
                self._buckets[key] = (tokens, now)
                return False
            self._buckets[key] = (tokens - 1, now)
            return True


_ingest = TokenBucket(rate_per_min=120)   # bridge: push frecuente
_command = TokenBucket(rate_per_min=60)   # dashboard: emisión de comandos


def limit_ingest(key: str) -> None:
    if not _ingest.check(key):
        raise HTTPException(status_code=429, detail="rate limit (ingest)")


def limit_command(key: str) -> None:
    if not _command.check(key):
        raise HTTPException(status_code=429, detail="rate limit (commands)")

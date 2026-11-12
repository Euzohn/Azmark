"""In-process rate limiting (spec #69, #70).

Azmark is self-hosted as a single API container, so a process-local sliding
window is sufficient; swapping in Redis later only touches this module. JWT
sessions are deliberately not limited here — they belong to a human using the
web UI, while tokens belong to agents that may loop (spec #69).

The anonymous auth routes (login/register) get their own per-client-IP
budgets: they are the only endpoints a walk-in attacker can hammer without
credentials, and the budgets blunt password brute-forcing and scripted
self-registration.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

from app.core.config import settings


class SlidingWindowLimiter:
    """Allow at most ``limit`` hits per ``window_seconds`` for each key."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                bucket = deque()
                self._hits[key] = bucket
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            if len(self._hits) > 2048:
                self._prune(cutoff)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _prune(self, cutoff: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in stale:
            del self._hits[key]


# One bucket per personal access token, shared by the REST API and MCP so an
# agent cannot double its budget by switching surfaces (spec #69).
access_token_limiter = SlidingWindowLimiter(settings.pat_rate_limit_per_minute)

# One bucket per client IP for the anonymous auth routes (spec #70).  The call
# sites skip the check when the corresponding setting is 0.
login_limiter = SlidingWindowLimiter(settings.login_rate_limit_per_minute)
register_limiter = SlidingWindowLimiter(settings.register_rate_limit_per_minute)

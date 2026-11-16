"""Simple in-process sliding-window rate limiter for sensitive ops mutations."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimitExceeded(Exception):
    def __init__(self, *, retry_after_sec: float) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after_sec = retry_after_sec


class SlidingWindowRateLimiter:
    """Per-key sliding window. Suitable for single-process API workers."""

    def __init__(self, *, max_requests: int, window_sec: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_sec <= 0:
            raise ValueError("window_sec must be positive")
        self._max = max_requests
        self._window = window_sec
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._max:
                retry = self._window - (now - bucket[0])
                raise RateLimitExceeded(retry_after_sec=max(0.1, retry))
            bucket.append(now)


# Agent settings mutations: 20 updates / minute / actor.
AGENT_SETTINGS_RATE_LIMITER = SlidingWindowRateLimiter(max_requests=20, window_sec=60.0)

# Auth surfaces (in-process; multi-replica deploys should also rate-limit at the edge).
AUTH_LOGIN_RATE_LIMITER = SlidingWindowRateLimiter(max_requests=20, window_sec=60.0)
AUTH_SIGNUP_RATE_LIMITER = SlidingWindowRateLimiter(max_requests=10, window_sec=3600.0)
# Signup field validation (debounced client-side; still bound per IP).
AUTH_SIGNUP_VALIDATE_RATE_LIMITER = SlidingWindowRateLimiter(
    max_requests=30, window_sec=60.0
)

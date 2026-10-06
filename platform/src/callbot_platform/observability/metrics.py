"""Lightweight in-process metrics for Phase 2 observability."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OutboxMetrics:
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    latency_ms_total: float = 0.0
    latency_samples: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counts[name] += n
        logger.info("metric_inc", extra={"metric": name, "delta": n})

    def observe_latency_ms(self, value: float) -> None:
        with self._lock:
            self.latency_ms_total += value
            self.latency_samples += 1
        logger.info(
            "metric_latency",
            extra={"metric": "outbox_processing_latency_ms", "value": round(value, 2)},
        )

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            avg = (
                self.latency_ms_total / self.latency_samples
                if self.latency_samples
                else 0.0
            )
            return {
                **dict(self.counts),
                "outbox_processing_latency_ms_avg": round(avg, 2),
            }


@dataclass
class ApiMetrics:
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counts[name] += n

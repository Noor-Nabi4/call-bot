"""Shared worker lifecycle helpers (SIGTERM, bounded drain)."""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class StoppableWorker(Protocol):
    def request_stop(self) -> None: ...

    def run_forever(self) -> None: ...


def install_signal_handlers(worker: StoppableWorker) -> None:
    def _stop(*_args: object) -> None:
        logger.info("worker_shutdown_requested")
        worker.request_stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)


def run_with_graceful_shutdown(
    worker: StoppableWorker,
    *,
    shutdown_timeout_seconds: float = 30.0,
    after_stop: Callable[[], None] | None = None,
) -> None:
    """
    Run until stop requested. Workers must stop claiming new work on request_stop
    and finish the current item when possible.
    """
    install_signal_handlers(worker)
    started = time.monotonic()
    try:
        worker.run_forever()
    finally:
        elapsed = time.monotonic() - started
        logger.info(
            "worker_stopped",
            extra={
                "elapsed_seconds": round(elapsed, 2),
                "shutdown_timeout_seconds": shutdown_timeout_seconds,
            },
        )
        if after_stop is not None:
            after_stop()

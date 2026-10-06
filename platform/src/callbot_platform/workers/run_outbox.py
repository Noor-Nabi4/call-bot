"""CLI entry: python -m callbot_platform.workers.run_outbox"""

from __future__ import annotations

import logging
import sys

from callbot_platform.config import get_settings
from callbot_platform.db import get_session_factory
from callbot_platform.workers.lifecycle import run_with_graceful_shutdown
from callbot_platform.workers.outbox import NotificationOutboxWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("outbox_worker")


def main() -> int:
    settings = get_settings()
    worker = NotificationOutboxWorker(get_session_factory(), settings=settings)
    logger.info(
        "outbox_worker_starting",
        extra={
            "batch_size": settings.outbox_batch_size,
            "poll_interval": settings.outbox_poll_interval_seconds,
        },
    )
    run_with_graceful_shutdown(
        worker, shutdown_timeout_seconds=float(settings.job_shutdown_timeout_seconds)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

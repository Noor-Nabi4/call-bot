"""CLI entry: python -m callbot_platform.workers.run_outbox"""

from __future__ import annotations

import logging
import signal
import sys

from callbot_platform.config import get_settings
from callbot_platform.db import get_session_factory
from callbot_platform.workers.outbox import NotificationOutboxWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("outbox_worker")


def main() -> int:
    settings = get_settings()
    worker = NotificationOutboxWorker(get_session_factory(), settings=settings)

    def _stop(*_args: object) -> None:
        logger.info("outbox_worker_shutdown_requested")
        worker.request_stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    logger.info(
        "outbox_worker_starting",
        extra={
            "batch_size": settings.outbox_batch_size,
            "poll_interval": settings.outbox_poll_interval_seconds,
        },
    )
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

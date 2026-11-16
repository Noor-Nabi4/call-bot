"""CLI entry: python -m callbot_platform.workers.run_jobs"""

from __future__ import annotations

import logging
import sys

from callbot_platform.async_jobs.handlers import attach_default_handlers
from callbot_platform.async_jobs.worker import AsyncJobWorker
from callbot_platform.config import get_settings
from callbot_platform.db import get_session_factory
from callbot_platform.workers.lifecycle import run_with_graceful_shutdown

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("job_worker")


def main() -> int:
    settings = get_settings()
    worker = AsyncJobWorker(get_session_factory(), settings=settings)
    attach_default_handlers(worker, settings=settings)
    logger.info(
        "job_worker_starting",
        extra={
            "batch_size": settings.job_batch_size,
            "poll_interval": settings.job_poll_interval_seconds,
            "lease_seconds": settings.job_lease_seconds,
        },
    )
    run_with_graceful_shutdown(
        worker, shutdown_timeout_seconds=float(settings.job_shutdown_timeout_seconds)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""CLI entry: python -m callbot_platform.workers.run_outbox

Drains both notification_outbox and inventory_outbox_events.
"""

from __future__ import annotations

import logging
import sys
import time

from callbot_platform.config import get_settings
from callbot_platform.db import get_session_factory
from callbot_platform.workers.inventory_outbox import InventoryOutboxWorker
from callbot_platform.workers.lifecycle import install_signal_handlers
from callbot_platform.workers.outbox import NotificationOutboxWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("outbox_worker")


class CombinedOutboxWorker:
    """Poll inventory domain outbox then notification delivery outbox."""

    def __init__(
        self,
        inventory_worker: InventoryOutboxWorker,
        notification_worker: NotificationOutboxWorker,
        *,
        poll_interval_seconds: float,
    ) -> None:
        self._inventory = inventory_worker
        self._notification = notification_worker
        self._interval = poll_interval_seconds
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True
        self._inventory.request_stop()
        self._notification.request_stop()

    def run_forever(self) -> None:
        while not self._stop:
            inv_n = self._inventory.process_batch()
            notif_n = self._notification.process_batch()
            if inv_n == 0 and notif_n == 0:
                time.sleep(self._interval)


def main() -> int:
    settings = get_settings()
    factory = get_session_factory()
    inventory_worker = InventoryOutboxWorker(factory, settings=settings)
    notification_worker = NotificationOutboxWorker(factory, settings=settings)
    worker = CombinedOutboxWorker(
        inventory_worker,
        notification_worker,
        poll_interval_seconds=float(settings.outbox_poll_interval_seconds),
    )
    logger.info(
        "outbox_worker_starting",
        extra={
            "batch_size": settings.outbox_batch_size,
            "poll_interval": settings.outbox_poll_interval_seconds,
            "drains": ["inventory_outbox_events", "notification_outbox"],
        },
    )
    install_signal_handlers(worker)
    worker.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())

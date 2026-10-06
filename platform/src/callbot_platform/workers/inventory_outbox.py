"""Inventory domain outbox worker — claim/process inventory_outbox_events."""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, text, update
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.inventory.constants import (
    ALERT_LOW_STOCK,
    ALERT_OUT_OF_STOCK,
    OUTBOX_LOW_STOCK,
    OUTBOX_OUT_OF_STOCK,
    OUTBOX_RELEASED,
    OUTBOX_RESERVED,
    OUTBOX_STOCK_CHANGED,
)
from callbot_platform.crm.inventory.notifications import InventoryNotificationService
from callbot_platform.db.models.inventory import (
    InventoryAlertEvent,
    InventoryBalance,
    InventoryItem,
    InventoryOutboxEvent,
)
from callbot_platform.tenancy import (
    TenantContext,
    TenantSource,
    clear_tenant_context,
    set_tenant_context,
)
from callbot_platform.workers.outbox import compute_backoff_seconds

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_PROCESSED = "processed"
STATUS_FAILED = "failed"
STATUS_DEAD = "dead_letter"

KNOWN_EVENT_TYPES = frozenset(
    {
        OUTBOX_STOCK_CHANGED,
        OUTBOX_RESERVED,
        OUTBOX_RELEASED,
        OUTBOX_LOW_STOCK,
        OUTBOX_OUT_OF_STOCK,
    }
)


class InventoryOutboxWorker:
    """
    Drain inventory_outbox_events safely across multiple replicas.

    Claim → commit → side effects (enqueue notification_outbox) → result update.
    Never holds row locks during notification enqueue sessions beyond claim TX.
    """

    def __init__(
        self,
        session_factory: Any,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._worker_id = (
            worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run_forever(self) -> None:
        interval = float(self._settings.outbox_poll_interval_seconds)
        while not self._stop:
            processed = self.process_batch()
            if processed == 0:
                time.sleep(interval)

    def process_batch(self) -> int:
        self._reclaim_expired_leases()
        claimed = self._claim_batch()
        if not claimed:
            return 0
        for row_id, tenant_id in claimed:
            if self._stop:
                break
            self._process_one(row_id, tenant_id)
        return len(claimed)

    def _reclaim_expired_leases(self) -> int:
        now = datetime.now(UTC)
        session: Session = self._session_factory()
        try:
            result = session.execute(
                update(InventoryOutboxEvent)
                .where(
                    InventoryOutboxEvent.status == STATUS_PROCESSING,
                    InventoryOutboxEvent.lease_expires_at.is_not(None),
                    InventoryOutboxEvent.lease_expires_at < now,
                )
                .values(
                    status=STATUS_PENDING,
                    claimed_at=None,
                    claimed_by=None,
                    lease_expires_at=None,
                    updated_at=now,
                    error="lease_expired_reclaimed",
                )
            )
            session.commit()
            return int(result.rowcount or 0)
        except Exception:
            session.rollback()
            logger.exception("inventory_outbox_lease_reclaim_failed")
            return 0
        finally:
            session.close()

    def _claim_batch(self) -> list[tuple[UUID, UUID]]:
        batch_size = int(self._settings.outbox_batch_size)
        now = datetime.now(UTC)
        lease = now + timedelta(seconds=float(self._settings.outbox_lease_seconds))
        session: Session = self._session_factory()
        try:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "postgresql":
                result = session.execute(
                    text(
                        """
                        SELECT id, tenant_id
                        FROM inventory_outbox_events
                        WHERE status = :pending
                          AND (next_attempt_at IS NULL OR next_attempt_at <= :now)
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT :limit
                        """
                    ),
                    {
                        "pending": STATUS_PENDING,
                        "now": now,
                        "limit": batch_size,
                    },
                )
                rows = [(UUID(str(r[0])), UUID(str(r[1]))) for r in result.fetchall()]
            else:
                q = (
                    select(InventoryOutboxEvent)
                    .where(
                        InventoryOutboxEvent.status == STATUS_PENDING,
                        or_(
                            InventoryOutboxEvent.next_attempt_at.is_(None),
                            InventoryOutboxEvent.next_attempt_at <= now,
                        ),
                    )
                    .order_by(InventoryOutboxEvent.created_at.asc())
                    .limit(batch_size)
                    .with_for_update()
                )
                objs = list(session.scalars(q).all())
                rows = [(o.id, o.tenant_id) for o in objs]

            if not rows:
                session.commit()
                return []

            ids = [r[0] for r in rows]
            session.execute(
                update(InventoryOutboxEvent)
                .where(
                    InventoryOutboxEvent.id.in_(ids),
                    InventoryOutboxEvent.status == STATUS_PENDING,
                )
                .values(
                    status=STATUS_PROCESSING,
                    claimed_at=now,
                    claimed_by=self._worker_id,
                    lease_expires_at=lease,
                    updated_at=now,
                )
            )
            session.commit()
            return rows
        except Exception:
            session.rollback()
            logger.exception(
                "inventory_outbox_claim_failed",
                extra={"worker_id": self._worker_id},
            )
            raise
        finally:
            session.close()

    def _process_one(self, row_id: UUID, tenant_id: UUID) -> None:
        token = set_tenant_context(
            TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)
        )
        try:
            session: Session = self._session_factory()
            try:
                row = session.get(InventoryOutboxEvent, row_id)
                if row is None or row.status != STATUS_PROCESSING:
                    session.commit()
                    return
                if row.tenant_id != tenant_id:
                    row.status = STATUS_DEAD
                    row.error = "tenant_mismatch"
                    row.updated_at = datetime.now(UTC)
                    session.commit()
                    return

                if row.event_type not in KNOWN_EVENT_TYPES:
                    row.status = STATUS_DEAD
                    row.error = f"unknown_event_type:{row.event_type}"
                    row.updated_at = datetime.now(UTC)
                    session.commit()
                    return

                self._handle_event(session, row)
                now = datetime.now(UTC)
                row.status = STATUS_PROCESSED
                row.processed_at = now
                row.error = None
                row.claimed_at = None
                row.claimed_by = None
                row.lease_expires_at = None
                row.updated_at = now
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.exception(
                    "inventory_outbox_process_failed",
                    extra={
                        "outbox_id": str(row_id),
                        "tenant_id": str(tenant_id),
                    },
                )
                self._mark_failure(row_id, tenant_id, str(exc)[:500])
            finally:
                session.close()
        finally:
            clear_tenant_context(token)

    def _handle_event(self, session: Session, row: InventoryOutboxEvent) -> None:
        if row.event_type not in {OUTBOX_LOW_STOCK, OUTBOX_OUT_OF_STOCK}:
            # Stock/reserve/release events are durable for future ops/analytics.
            return

        payload = dict(row.payload or {})
        alert_event_id_raw = payload.get("alert_event_id")
        if not alert_event_id_raw:
            return
        alert_event_id = UUID(str(alert_event_id_raw))
        alert = session.scalar(
            select(InventoryAlertEvent).where(
                InventoryAlertEvent.tenant_id == row.tenant_id,
                InventoryAlertEvent.id == alert_event_id,
            )
        )
        if alert is None:
            return
        if alert.email_notification_status in {"queued", "sent", "skipped"}:
            # Idempotent retry: notification already enqueued.
            return

        item = session.scalar(
            select(InventoryItem).where(
                InventoryItem.tenant_id == row.tenant_id,
                InventoryItem.id == alert.inventory_item_id,
            )
        )
        balance = session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.tenant_id == row.tenant_id,
                InventoryBalance.inventory_item_id == alert.inventory_item_id,
                InventoryBalance.location_id == alert.location_id,
            )
        )
        if item is None or balance is None:
            alert.email_notification_status = "skipped"
            return

        alert_type = (
            ALERT_OUT_OF_STOCK
            if row.event_type == OUTBOX_OUT_OF_STOCK
            else ALERT_LOW_STOCK
        )
        InventoryNotificationService(session).enqueue_low_stock_email(
            tenant_id=row.tenant_id,
            item=item,
            balance=balance,
            alert_type=alert_type,
            alert_event_id=alert.id,
        )
        alert.email_notification_status = "queued"

    def _mark_failure(self, row_id: UUID, tenant_id: UUID, error: str) -> None:
        settings = self._settings
        max_retries = int(settings.outbox_max_retries)
        base = float(settings.outbox_base_backoff_seconds)
        cap = float(settings.outbox_max_backoff_seconds)
        now = datetime.now(UTC)
        session = self._session_factory()
        try:
            row = session.get(InventoryOutboxEvent, row_id)
            if row is None or row.tenant_id != tenant_id:
                session.commit()
                return
            row.attempt_count = int(row.attempt_count or 0) + 1
            row.error = error
            row.updated_at = now
            row.last_failed_at = now
            if row.first_failed_at is None:
                row.first_failed_at = now
            if row.attempt_count >= max_retries:
                row.status = STATUS_DEAD
                row.next_attempt_at = None
            else:
                delay = compute_backoff_seconds(row.attempt_count, base=base, cap=cap)
                row.status = STATUS_PENDING
                row.next_attempt_at = now + timedelta(seconds=delay)
                row.claimed_at = None
                row.claimed_by = None
                row.lease_expires_at = None
            session.commit()
        finally:
            session.close()

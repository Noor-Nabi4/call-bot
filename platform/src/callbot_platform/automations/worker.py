"""Claim/process automation_events and due scheduled reminders."""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from callbot_platform.automations.engine import AutomationEngine
from callbot_platform.automations.events import emit_automation_event
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.automations import (
    AutomationEvent,
    AutomationScheduledEvent,
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


class AutomationEventWorker:
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
            n = self.process_batch()
            if n == 0:
                time.sleep(interval)

    def process_batch(self) -> int:
        self._emit_due_reminders()
        self._reclaim_expired_leases()
        claimed = self._claim_batch()
        for event_id, tenant_id in claimed:
            if self._stop:
                break
            self._process_one(event_id, tenant_id)
        return len(claimed)

    def _emit_due_reminders(self) -> int:
        now = datetime.now(UTC)
        session: Session = self._session_factory()
        emitted = 0
        try:
            lease = now + timedelta(seconds=float(self._settings.outbox_lease_seconds))
            rows = list(
                session.scalars(
                    select(AutomationScheduledEvent)
                    .where(
                        AutomationScheduledEvent.status == "pending",
                        AutomationScheduledEvent.due_at <= now,
                    )
                    .order_by(AutomationScheduledEvent.due_at.asc())
                    .limit(int(self._settings.outbox_batch_size))
                    .with_for_update(skip_locked=True)
                ).all()
            )
            for row in rows:
                row.status = "processing"
                row.claimed_at = now
                row.claimed_by = self._worker_id
                row.lease_expires_at = lease
                row.updated_at = now
            session.commit()
            ids = [(r.id, r.tenant_id) for r in rows]
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        for sched_id, tenant_id in ids:
            s: Session = self._session_factory()
            try:
                set_tenant_context(
                    TenantContext(tenant_id=tenant_id, source=TenantSource.SYSTEM)
                )
                row = s.get(AutomationScheduledEvent, sched_id)
                if row is None or row.status != "processing":
                    continue
                event = emit_automation_event(
                    s,
                    tenant_id=tenant_id,
                    event_type=row.event_type,
                    source="scheduler",
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    payload=row.payload or {},
                    idempotency_key=f"sched-emit:{row.id}",
                )
                row.status = "emitted"
                row.emitted_event_id = event.id if event else None
                row.updated_at = datetime.now(UTC)
                s.commit()
                emitted += 1
            except Exception:
                s.rollback()
                logger.exception("reminder_emit_failed id=%s", sched_id)
            finally:
                clear_tenant_context()
                s.close()
        return emitted

    def _reclaim_expired_leases(self) -> int:
        now = datetime.now(UTC)
        session: Session = self._session_factory()
        try:
            result = session.execute(
                update(AutomationEvent)
                .where(
                    AutomationEvent.status == STATUS_PROCESSING,
                    AutomationEvent.lease_expires_at.is_not(None),
                    AutomationEvent.lease_expires_at < now,
                )
                .values(
                    status=STATUS_PENDING,
                    claimed_at=None,
                    claimed_by=None,
                    lease_expires_at=None,
                    updated_at=now,
                )
            )
            session.commit()
            return int(result.rowcount or 0)
        finally:
            session.close()

    def _claim_batch(self) -> list[tuple[UUID, UUID]]:
        now = datetime.now(UTC)
        lease = now + timedelta(seconds=float(self._settings.outbox_lease_seconds))
        session: Session = self._session_factory()
        try:
            rows = list(
                session.scalars(
                    select(AutomationEvent)
                    .where(
                        AutomationEvent.status == STATUS_PENDING,
                        or_(
                            AutomationEvent.next_attempt_at.is_(None),
                            AutomationEvent.next_attempt_at <= now,
                        ),
                    )
                    .order_by(AutomationEvent.created_at.asc())
                    .limit(int(self._settings.outbox_batch_size))
                    .with_for_update(skip_locked=True)
                ).all()
            )
            claimed: list[tuple[UUID, UUID]] = []
            for row in rows:
                row.status = STATUS_PROCESSING
                row.claimed_at = now
                row.claimed_by = self._worker_id
                row.lease_expires_at = lease
                row.attempt_count = int(row.attempt_count or 0) + 1
                row.updated_at = now
                claimed.append((row.id, row.tenant_id))
            session.commit()
            return claimed
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _process_one(self, event_id: UUID, tenant_id: UUID) -> None:
        session: Session = self._session_factory()
        try:
            set_tenant_context(
                TenantContext(tenant_id=tenant_id, source=TenantSource.SYSTEM)
            )
            event = session.get(AutomationEvent, event_id)
            if event is None or event.tenant_id != tenant_id:
                return
            AutomationEngine(session).process_event(event)
            session.commit()
            logger.info(
                "automation_execution_completed event_id=%s tenant_id=%s",
                event_id,
                tenant_id,
            )
        except Exception as exc:
            session.rollback()
            self._mark_failure(event_id, tenant_id, str(exc))
            logger.exception("automation_event_failed event_id=%s", event_id)
        finally:
            clear_tenant_context()
            session.close()

    def _mark_failure(self, event_id: UUID, tenant_id: UUID, error: str) -> None:
        session: Session = self._session_factory()
        try:
            event = session.get(AutomationEvent, event_id)
            if event is None:
                return
            max_retries = int(self._settings.outbox_max_retries)
            now = datetime.now(UTC)
            if int(event.attempt_count or 0) >= max_retries:
                event.status = STATUS_DEAD
                event.error = error[:2000]
            else:
                event.status = STATUS_PENDING
                event.error = error[:2000]
                event.next_attempt_at = now + timedelta(
                    seconds=compute_backoff_seconds(
                        int(event.attempt_count or 1),
                        base=float(self._settings.outbox_base_backoff_seconds),
                        cap=float(self._settings.outbox_max_backoff_seconds),
                    )
                )
            event.claimed_at = None
            event.claimed_by = None
            event.lease_expires_at = None
            event.updated_at = now
            session.commit()
        finally:
            session.close()

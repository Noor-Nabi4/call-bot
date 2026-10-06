"""Outbound notification / webhook delivery outbox worker."""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import NotificationOutbox
from callbot_platform.observability.metrics import OutboxMetrics
from callbot_platform.tenancy import (
    TenantContext,
    TenantSource,
    clear_tenant_context,
    set_tenant_context,
)

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_DEAD = "dead_letter"
STATUS_SKIPPED = "skipped"


class _SkipDeliveryError(Exception):
    """Provider not configured — mark skipped, not failed."""


def compute_backoff_seconds(
    attempt_count: int,
    *,
    base: float,
    cap: float,
) -> float:
    """Exponential backoff after a failed attempt (attempt_count is post-increment)."""
    exp = max(0, attempt_count - 1)
    return min(cap, base * (2**exp))


def count_by_status(session: Session, status: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(NotificationOutbox)
            .where(NotificationOutbox.status == status)
        )
        or 0
    )


class NotificationOutboxWorker:
    """
    Drain notification_outbox safely across multiple replicas.

    Claim → commit → external I/O → result update.
    Never holds row locks during provider HTTP.
    """

    def __init__(
        self,
        session_factory: Any,
        *,
        settings: Settings | None = None,
        sms_sender: Any | None = None,
        webhook_sender: Any | None = None,
        email_sender: Any | None = None,
        worker_id: str | None = None,
        metrics: OutboxMetrics | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings or get_settings()
        self._sms_sender = sms_sender
        self._webhook_sender = webhook_sender
        self._email_sender = email_sender
        self._worker_id = (
            worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self._metrics = metrics or OutboxMetrics()
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
                update(NotificationOutbox)
                .where(
                    NotificationOutbox.status == STATUS_PROCESSING,
                    NotificationOutbox.lease_expires_at.is_not(None),
                    NotificationOutbox.lease_expires_at < now,
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
            count = int(result.rowcount or 0)
            if count:
                self._metrics.inc("outbox_lease_reclaimed_total", count)
            return count
        except Exception:
            session.rollback()
            logger.exception("outbox_lease_reclaim_failed")
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
                        FROM notification_outbox
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
                    select(NotificationOutbox)
                    .where(
                        NotificationOutbox.status == STATUS_PENDING,
                        or_(
                            NotificationOutbox.next_attempt_at.is_(None),
                            NotificationOutbox.next_attempt_at <= now,
                        ),
                    )
                    .order_by(NotificationOutbox.created_at.asc())
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
                update(NotificationOutbox)
                .where(
                    NotificationOutbox.id.in_(ids),
                    NotificationOutbox.status == STATUS_PENDING,
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
            self._metrics.inc("outbox_processing_count", len(rows))
            return rows
        except Exception:
            session.rollback()
            logger.exception(
                "outbox_claim_failed", extra={"worker_id": self._worker_id}
            )
            raise
        finally:
            session.close()

    def _process_one(self, row_id: UUID, tenant_id: UUID) -> None:
        started = time.perf_counter()
        token = set_tenant_context(
            TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)
        )
        channel = "unknown"
        try:
            loaded = self._load_claimed(row_id, tenant_id)
            if loaded is None:
                return
            channel, to_address, body, payload, idem, _provider_ref = loaded
            # Delivery happens outside any claim lock (session already closed).
            try:
                provider_ref = self._deliver(
                    channel=channel,
                    tenant_id=tenant_id,
                    to_address=to_address,
                    body=body,
                    payload=payload,
                    idempotency_key=idem,
                )
                self._mark_success(row_id, tenant_id, provider_ref)
                self._metrics.inc("outbox_success_count")
            except _SkipDeliveryError as exc:
                self._mark_skipped(row_id, tenant_id, str(exc))
            except Exception as exc:
                logger.exception(
                    "outbox_delivery_failed",
                    extra={
                        "outbox_id": str(row_id),
                        "tenant_id": str(tenant_id),
                        "channel": channel,
                    },
                )
                self._mark_failure(row_id, tenant_id, str(exc)[:500])
                self._metrics.inc("outbox_failure_count")
        finally:
            clear_tenant_context(token)
            self._metrics.observe_latency_ms((time.perf_counter() - started) * 1000)

    def _load_claimed(
        self, row_id: UUID, tenant_id: UUID
    ) -> tuple[str, str, str, dict[str, Any], str, str | None] | None:
        session: Session = self._session_factory()
        try:
            row = session.get(NotificationOutbox, row_id)
            if row is None or row.status != STATUS_PROCESSING:
                session.commit()
                return None
            if row.tenant_id != tenant_id:
                logger.error(
                    "outbox_tenant_mismatch",
                    extra={
                        "outbox_id": str(row_id),
                        "expected": str(tenant_id),
                        "actual": str(row.tenant_id),
                    },
                )
                row.status = STATUS_DEAD
                row.error = "tenant_mismatch"
                row.updated_at = datetime.now(UTC)
                session.commit()
                self._metrics.inc("outbox_dead_letter_count")
                return None

            # Snapshot fields then close session before external I/O.
            data = (
                row.channel,
                row.to_address,
                row.body,
                dict(row.payload or {}),
                row.idempotency_key or str(row.id),
                row.provider_ref,
            )
            session.commit()
            return data
        except Exception:
            session.rollback()
            logger.exception("outbox_load_failed", extra={"outbox_id": str(row_id)})
            return None
        finally:
            session.close()

    def _deliver(
        self,
        *,
        channel: str,
        tenant_id: UUID,
        to_address: str,
        body: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> str | None:
        if channel == "sms":
            return self._deliver_sms(
                tenant_id=tenant_id,
                to=to_address,
                body=body,
                idempotency_key=idempotency_key,
            )
        if channel == "email":
            return self._deliver_email(
                tenant_id=tenant_id,
                to=to_address,
                body=body,
                idempotency_key=idempotency_key,
            )
        if channel == "webhook":
            return self._deliver_webhook(
                tenant_id=tenant_id,
                payload=payload,
                idempotency_key=idempotency_key,
            )
        raise ValueError(f"unsupported_channel:{channel}")

    def _deliver_sms(
        self,
        *,
        tenant_id: UUID,
        to: str,
        body: str,
        idempotency_key: str,
    ) -> str | None:
        if self._sms_sender is not None:
            return self._sms_sender(
                tenant_id=tenant_id,
                to=to,
                body=body,
                idempotency_key=idempotency_key,
            )
        from callbot_platform.scheduling.notifications import NotificationService

        session = self._session_factory()
        try:
            svc = NotificationService(session, settings=self._settings)
            sid = svc.send_sms_now(
                tenant_id=tenant_id,
                to=to,
                body=body,
                idempotency_key=idempotency_key,
            )
            session.commit()
            if sid is None:
                raise _SkipDeliveryError("twilio_not_configured")
            return sid
        finally:
            session.close()

    def _deliver_email(
        self,
        *,
        tenant_id: UUID,
        to: str,
        body: str,
        idempotency_key: str,
    ) -> str | None:
        if self._email_sender is not None:
            return self._email_sender(
                tenant_id=tenant_id,
                to=to,
                body=body,
                idempotency_key=idempotency_key,
            )
        raise _SkipDeliveryError("email_provider_not_configured")

    def _deliver_webhook(
        self,
        *,
        tenant_id: UUID,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> str | None:
        if self._webhook_sender is not None:
            return self._webhook_sender(
                tenant_id=tenant_id,
                payload=payload,
                idempotency_key=idempotency_key,
            )
        from callbot_platform.automation.webhooks import deliver_webhook

        url = str(payload.get("url") or "")
        secret = payload.get("secret")
        event = str(payload.get("event") or "automation")
        timeout_sec = float(payload.get("timeout_sec") or 15)
        event_payload = payload.get("event_payload") or {}
        if isinstance(event_payload, str):
            event_payload = {"body": event_payload}
        result = deliver_webhook(
            url=url,
            payload=event_payload,
            secret=str(secret) if secret else None,
            timeout_sec=timeout_sec,
            event=event,
            tenant_id=str(tenant_id),
            rule_id=str(payload.get("rule_id") or ""),
        )
        status_code = result.get("status_code")
        return f"http:{status_code}:{idempotency_key}"

    def _mark_success(
        self, row_id: UUID, tenant_id: UUID, provider_ref: str | None
    ) -> None:
        session = self._session_factory()
        try:
            row = session.get(NotificationOutbox, row_id)
            if row is None or row.tenant_id != tenant_id:
                session.commit()
                return
            row.status = STATUS_SENT
            row.provider_ref = provider_ref
            row.error = None
            row.updated_at = datetime.now(UTC)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _mark_skipped(self, row_id: UUID, tenant_id: UUID, reason: str) -> None:
        session = self._session_factory()
        try:
            row = session.get(NotificationOutbox, row_id)
            if row is None or row.tenant_id != tenant_id:
                session.commit()
                return
            row.status = STATUS_SKIPPED
            row.error = reason[:500]
            row.updated_at = datetime.now(UTC)
            session.commit()
        finally:
            session.close()

    def _mark_failure(self, row_id: UUID, tenant_id: UUID, error: str) -> None:
        settings = self._settings
        max_retries = int(settings.outbox_max_retries)
        base = float(settings.outbox_base_backoff_seconds)
        cap = float(settings.outbox_max_backoff_seconds)
        now = datetime.now(UTC)
        session = self._session_factory()
        try:
            row = session.get(NotificationOutbox, row_id)
            if row is None or row.tenant_id != tenant_id:
                session.commit()
                return
            row.attempt_count = int(row.attempt_count or 0) + 1
            row.error = error
            row.updated_at = now
            if row.attempt_count >= max_retries:
                row.status = STATUS_DEAD
                row.next_attempt_at = None
                self._metrics.inc("outbox_dead_letter_count")
            else:
                delay = compute_backoff_seconds(row.attempt_count, base=base, cap=cap)
                row.status = STATUS_PENDING
                row.next_attempt_at = now + timedelta(seconds=delay)
                row.claimed_at = None
                row.claimed_by = None
                row.lease_expires_at = None
                self._metrics.inc("outbox_retry_count")
            row.last_failed_at = now
            if row.first_failed_at is None:
                row.first_failed_at = now
            session.commit()
        finally:
            session.close()

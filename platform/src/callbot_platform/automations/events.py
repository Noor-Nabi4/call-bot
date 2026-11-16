"""Durable automation event emission (same TX as domain mutation)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.automations.constants import (
    DEFAULT_APPOINTMENT_REMINDER_HOURS,
    EVENT_TYPES,
    MAX_AUTOMATION_DEPTH,
    AutomationEventType,
)
from callbot_platform.db.models.automations import (
    AutomationEvent,
    AutomationScheduledEvent,
)

logger = logging.getLogger(__name__)


class AutomationEventError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def emit_automation_event(
    session: Session,
    *,
    tenant_id: UUID,
    event_type: str,
    source: str,
    entity_type: str,
    entity_id: UUID,
    payload: dict[str, Any] | None = None,
    idempotency_key: str,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
    automation_execution_id: UUID | None = None,
    automation_depth: int = 0,
    occurred_at: datetime | None = None,
) -> AutomationEvent | None:
    """
    Insert a durable automation event in the current transaction.

    Returns existing row on idempotent replay. Returns None when suppressed for
    loop protection (depth exceeded).
    """
    if event_type not in EVENT_TYPES:
        raise AutomationEventError("invalid_event_type", f"Unknown event: {event_type}")
    key = (idempotency_key or "").strip()[:191]
    if not key:
        raise AutomationEventError(
            "invalid_idempotency_key", "idempotency_key required"
        )

    if automation_depth > MAX_AUTOMATION_DEPTH:
        logger.warning(
            "automation_event_suppressed_depth tenant_id=%s event_type=%s depth=%s",
            tenant_id,
            event_type,
            automation_depth,
        )
        return None

    existing = session.scalar(
        select(AutomationEvent).where(
            AutomationEvent.tenant_id == tenant_id,
            AutomationEvent.idempotency_key == key,
        )
    )
    if existing is not None:
        return existing

    row = AutomationEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(UTC),
        source=source[:64],
        entity_type=entity_type[:64],
        entity_id=entity_id,
        payload=dict(payload or {}),
        correlation_id=correlation_id or uuid.uuid4(),
        causation_id=causation_id,
        automation_execution_id=automation_execution_id,
        automation_depth=max(0, int(automation_depth)),
        status="pending",
        idempotency_key=key,
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        session.expire_all()
        existing = session.scalar(
            select(AutomationEvent).where(
                AutomationEvent.tenant_id == tenant_id,
                AutomationEvent.idempotency_key == key,
            )
        )
        if existing is None:
            raise
        return existing

    logger.info(
        "automation_event_received tenant_id=%s event_id=%s event_type=%s",
        tenant_id,
        row.id,
        event_type,
    )
    return row


def schedule_appointment_reminder(
    session: Session,
    *,
    tenant_id: UUID,
    appointment_id: UUID,
    starts_at: datetime,
    payload: dict[str, Any],
    hours_before: int = DEFAULT_APPOINTMENT_REMINDER_HOURS,
) -> AutomationScheduledEvent | None:
    """Schedule durable APPOINTMENT_REMINDER emission before starts_at."""
    from datetime import timedelta

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    due = starts_at - timedelta(hours=max(1, hours_before))
    if due <= datetime.now(UTC):
        # Too soon — emit immediately as event instead of scheduling past due.
        emit_automation_event(
            session,
            tenant_id=tenant_id,
            event_type=AutomationEventType.APPOINTMENT_REMINDER.value,
            source="appointments",
            entity_type="appointment",
            entity_id=appointment_id,
            payload=payload,
            idempotency_key=f"appt-reminder:{appointment_id}:{hours_before}h",
        )
        return None

    key = f"appt-reminder:{appointment_id}:{hours_before}h"
    existing = session.scalar(
        select(AutomationScheduledEvent).where(
            AutomationScheduledEvent.tenant_id == tenant_id,
            AutomationScheduledEvent.idempotency_key == key,
        )
    )
    if existing is not None:
        if existing.status == "pending":
            existing.due_at = due
            existing.payload = dict(payload)
            existing.updated_at = datetime.now(UTC)
        return existing

    row = AutomationScheduledEvent(
        tenant_id=tenant_id,
        event_type=AutomationEventType.APPOINTMENT_REMINDER.value,
        entity_type="appointment",
        entity_id=appointment_id,
        due_at=due,
        payload=dict(payload),
        status="pending",
        idempotency_key=key,
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        return session.scalar(
            select(AutomationScheduledEvent).where(
                AutomationScheduledEvent.tenant_id == tenant_id,
                AutomationScheduledEvent.idempotency_key == key,
            )
        )
    return row


def cancel_appointment_reminders(
    session: Session, *, tenant_id: UUID, appointment_id: UUID
) -> None:
    rows = session.scalars(
        select(AutomationScheduledEvent).where(
            AutomationScheduledEvent.tenant_id == tenant_id,
            AutomationScheduledEvent.entity_id == appointment_id,
            AutomationScheduledEvent.status == "pending",
        )
    ).all()
    now = datetime.now(UTC)
    for row in rows:
        row.status = "cancelled"
        row.updated_at = now

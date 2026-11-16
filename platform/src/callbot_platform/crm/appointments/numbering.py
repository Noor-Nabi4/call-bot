"""Concurrency-safe tenant-scoped appointment number allocation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.db.models.scheduling import AppointmentNumberCounter


def allocate_appointment_number(session: Session, tenant_id: UUID) -> str:
    """Return next APT-###### for the tenant. Safe under concurrent writers."""
    row = session.scalar(
        select(AppointmentNumberCounter)
        .where(AppointmentNumberCounter.tenant_id == tenant_id)
        .with_for_update()
    )
    if row is None:
        row = AppointmentNumberCounter(tenant_id=tenant_id, last_value=0)
        try:
            with session.begin_nested():
                session.add(row)
                session.flush()
        except IntegrityError:
            row = session.scalar(
                select(AppointmentNumberCounter)
                .where(AppointmentNumberCounter.tenant_id == tenant_id)
                .with_for_update()
            )
            if row is None:
                raise RuntimeError("appointment number counter unavailable") from None
        else:
            row = session.scalar(
                select(AppointmentNumberCounter)
                .where(AppointmentNumberCounter.tenant_id == tenant_id)
                .with_for_update()
            )
            if row is None:
                raise RuntimeError("appointment number counter missing after insert")

    row.last_value += 1
    row.updated_at = datetime.now(UTC)
    session.flush()
    return f"APT-{row.last_value:06d}"

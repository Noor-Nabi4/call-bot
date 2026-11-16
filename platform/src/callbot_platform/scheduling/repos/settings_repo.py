"""Schedule settings repository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.db.models import (
    Tenant,
    TenantScheduleSettings,
    default_weekly_hours,
)
from callbot_platform.scheduling.errors import SchedulingError


class ScheduleSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, tenant_id: UUID) -> TenantScheduleSettings:
        row = self._session.scalar(
            select(TenantScheduleSettings).where(
                TenantScheduleSettings.tenant_id == tenant_id
            )
        )
        if row is not None:
            return row
        try:
            # The row must be added *inside* the nested transaction: entering
            # begin_nested() flushes any already-pending objects first (to
            # snapshot state before the SAVEPOINT), so adding beforehand
            # would raise the IntegrityError outside the savepoint and
            # poison the whole session instead of being caught here. Two
            # concurrent "first appointment for this tenant" requests can
            # both pass the SELECT above and race on this INSERT.
            with self._session.begin_nested():
                row = TenantScheduleSettings(
                    tenant_id=tenant_id,
                    timezone=None,
                    slot_minutes=60,
                    booking_horizon_days=14,
                    weekly_hours=default_weekly_hours(),
                )
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            row = self._session.scalar(
                select(TenantScheduleSettings).where(
                    TenantScheduleSettings.tenant_id == tenant_id
                )
            )
            if row is None:
                raise
        return row

    def effective_timezone(self, tenant_id: UUID) -> str:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise SchedulingError("tenant_not_found", "Tenant not found")
        settings = self.get_or_create(tenant_id)
        return (settings.timezone or tenant.timezone or "UTC").strip() or "UTC"

    def serialize(self, row: TenantScheduleSettings, tenant: Tenant) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "timezone": row.timezone or tenant.timezone,
            "slot_minutes": row.slot_minutes,
            "booking_horizon_days": row.booking_horizon_days,
            "weekly_hours": row.weekly_hours,
        }

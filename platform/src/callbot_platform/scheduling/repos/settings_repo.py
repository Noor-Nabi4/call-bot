"""Schedule settings repository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
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
        row = TenantScheduleSettings(
            tenant_id=tenant_id,
            timezone=None,
            slot_minutes=60,
            booking_horizon_days=14,
            weekly_hours=default_weekly_hours(),
        )
        self._session.add(row)
        self._session.flush()
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

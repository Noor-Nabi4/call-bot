"""Server-derived warranty status (Phase 21)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from callbot_platform.crm.equipment.constants import WarrantyStatus
from callbot_platform.db.models.equipment import Equipment


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


class EquipmentWarrantyService:
    """Central warranty eligibility — do not duplicate date logic in controllers."""

    @staticmethod
    def status_at(
        equipment: Equipment, *, at: date | datetime | None = None
    ) -> str:
        start = _as_date(equipment.warranty_start_date)
        end = _as_date(equipment.warranty_end_date)
        if start is None and end is None:
            return WarrantyStatus.UNKNOWN.value
        today = _as_date(at) or datetime.now(UTC).date()
        if start is not None and today < start:
            return WarrantyStatus.NOT_ACTIVE.value
        if end is not None and today > end:
            return WarrantyStatus.EXPIRED.value
        if end is None and start is not None and today >= start:
            return WarrantyStatus.ACTIVE.value
        if start is None and end is not None and today <= end:
            return WarrantyStatus.ACTIVE.value
        if start is not None and end is not None and start <= today <= end:
            return WarrantyStatus.ACTIVE.value
        return WarrantyStatus.NOT_ACTIVE.value

    @classmethod
    def is_under_warranty(
        cls, equipment: Equipment, *, at: date | datetime | None = None
    ) -> bool:
        return cls.status_at(equipment, at=at) == WarrantyStatus.ACTIVE.value

    @classmethod
    def summary(
        cls, equipment: Equipment, *, at: date | datetime | None = None
    ) -> dict[str, Any]:
        today = _as_date(at) or datetime.now(UTC).date()
        end = _as_date(equipment.warranty_end_date)
        days_remaining = None
        if end is not None:
            days_remaining = (end - today).days
        return {
            "warranty_status": cls.status_at(equipment, at=today),
            "under_warranty": cls.is_under_warranty(equipment, at=today),
            "warranty_start_date": (
                equipment.warranty_start_date.isoformat()
                if equipment.warranty_start_date
                else None
            ),
            "warranty_end_date": (
                equipment.warranty_end_date.isoformat()
                if equipment.warranty_end_date
                else None
            ),
            "warranty_provider": equipment.warranty_provider,
            "days_remaining": days_remaining,
        }

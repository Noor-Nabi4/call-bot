"""Equipment list / search with offset pagination."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from callbot_platform.crm.equipment.constants import EquipmentStatus, WarrantyStatus
from callbot_platform.crm.equipment.serialize import serialize_equipment
from callbot_platform.crm.equipment.warranty import EquipmentWarrantyService
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.equipment import Equipment


class EquipmentSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        customer_id: UUID | None = None,
        location_id: UUID | None = None,
        status: str | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        serial_number: str | None = None,
        warranty_status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        filters = [Equipment.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Equipment.archived_at.is_(None))
            filters.append(Equipment.status != EquipmentStatus.REMOVED.value)
        if customer_id is not None:
            filters.append(Equipment.customer_id == customer_id)
        if location_id is not None:
            filters.append(Equipment.location_id == location_id)
        if status:
            st = status.strip().upper()
            if st not in {s.value for s in EquipmentStatus}:
                raise CrmError("invalid_status", f"Unknown status: {status}")
            filters.append(Equipment.status == st)
        if manufacturer and manufacturer.strip():
            filters.append(
                func.lower(Equipment.manufacturer).like(
                    f"%{manufacturer.strip().lower()}%"
                )
            )
        if model and model.strip():
            filters.append(
                func.lower(Equipment.model).like(f"%{model.strip().lower()}%")
            )
        if serial_number and serial_number.strip():
            norm = serial_number.strip().upper()
            filters.append(
                or_(
                    Equipment.serial_number_normalized == norm,
                    func.lower(func.coalesce(Equipment.serial_number, "")).like(
                        f"%{serial_number.strip().lower()}%"
                    ),
                )
            )
        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Equipment.manufacturer).like(term),
                    func.lower(Equipment.model).like(term),
                    func.lower(func.coalesce(Equipment.serial_number, "")).like(term),
                )
            )

        page = min(max(1, limit), 100)
        off = max(0, offset)
        rows = list(
            self._session.scalars(
                select(Equipment)
                .where(and_(*filters))
                .order_by(Equipment.created_at.desc(), Equipment.id.desc())
                .offset(off)
                .limit(page)
            ).all()
        )

        if warranty_status:
            want = warranty_status.strip().upper()
            if want not in {s.value for s in WarrantyStatus}:
                raise CrmError(
                    "invalid_warranty_status",
                    f"Unknown warranty_status: {warranty_status}",
                )
            rows = [
                r
                for r in rows
                if EquipmentWarrantyService.status_at(r) == want
            ]

        return {
            "equipment": [serialize_equipment(r) for r in rows],
            "limit": page,
            "offset": off,
        }

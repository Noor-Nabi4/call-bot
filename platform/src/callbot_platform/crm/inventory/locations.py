"""Inventory location CRUD."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory.constants import (
    DEFAULT_LOCATION_CODE,
    LOCATION_STATUSES,
    LOCATION_TYPES,
)
from callbot_platform.crm.inventory.serialize import serialize_location
from callbot_platform.db.models.inventory import InventoryBalance, InventoryLocation
from callbot_platform.telephony.audit import write_audit


def _normalize_code(code: str) -> str:
    return code.strip().upper()


class InventoryLocationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        limit = min(max(limit, 1), 200)
        q = select(InventoryLocation).where(InventoryLocation.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(InventoryLocation.archived_at.is_(None))
        if status:
            q = q.where(InventoryLocation.status == status.upper())
        if cursor:
            q = q.where(InventoryLocation.id > UUID(cursor))
        q = q.order_by(InventoryLocation.name.asc()).limit(limit + 1)
        rows = list(self._session.scalars(q).all())
        next_cursor = None
        if len(rows) > limit:
            next_cursor = str(rows[limit - 1].id)
            rows = rows[:limit]
        return {
            "locations": [serialize_location(r) for r in rows],
            "next_cursor": next_cursor,
        }

    def get(self, tenant_id: UUID, location_id: UUID) -> dict[str, Any]:
        return serialize_location(self.get_row(tenant_id, location_id))

    def get_row(
        self,
        tenant_id: UUID,
        location_id: UUID,
        *,
        require_active: bool = False,
    ) -> InventoryLocation:
        row = self._session.scalar(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == tenant_id,
                InventoryLocation.id == location_id,
            )
        )
        if row is None or row.archived_at is not None:
            raise CrmError("not_found", "Inventory location not found")
        if require_active and row.status != "ACTIVE":
            raise CrmError("location_inactive", "Inventory location is not active")
        return row

    def ensure_default(self, tenant_id: UUID, *, actor: str) -> InventoryLocation:
        row = self._session.scalar(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == tenant_id,
                InventoryLocation.is_default.is_(True),
                InventoryLocation.archived_at.is_(None),
            )
        )
        if row is not None:
            return row
        created = self.create(
            tenant_id,
            name="Primary",
            code=DEFAULT_LOCATION_CODE,
            location_type="OTHER",
            is_default=True,
            actor=actor,
        )
        return self.get_row(tenant_id, UUID(created["id"]))

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        code: str,
        description: str | None = None,
        location_type: str = "OTHER",
        status: str = "ACTIVE",
        is_default: bool = False,
        address_metadata: dict[str, Any] | None = None,
        actor: str,
    ) -> dict[str, Any]:
        cleaned_name = name.strip()
        norm_code = _normalize_code(code)
        if not cleaned_name or not norm_code:
            raise CrmError("invalid_location", "Name and code are required")
        ltype = location_type.strip().upper()
        if ltype not in LOCATION_TYPES:
            raise CrmError("invalid_location_type", "Invalid location type")
        stat = status.strip().upper()
        if stat not in LOCATION_STATUSES:
            raise CrmError("invalid_location_status", "Invalid location status")

        if is_default:
            self._clear_default(tenant_id)

        row = InventoryLocation(
            tenant_id=tenant_id,
            name=cleaned_name,
            code=code.strip(),
            code_normalized=norm_code,
            description=description.strip() if description else None,
            location_type=ltype,
            status=stat,
            is_default=is_default,
            address_metadata=address_metadata or {},
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="inventory.location.create",
            resource_ids={"location_id": str(row.id)},
        )
        return serialize_location(row)

    def update(
        self,
        tenant_id: UUID,
        location_id: UUID,
        *,
        actor: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        row = self.get_row(tenant_id, location_id)
        if "name" in fields and fields["name"] is not None:
            row.name = str(fields["name"]).strip()
        if "code" in fields and fields["code"] is not None:
            row.code = str(fields["code"]).strip()
            row.code_normalized = _normalize_code(row.code)
        if "description" in fields:
            row.description = (
                str(fields["description"]).strip() if fields["description"] else None
            )
        if "location_type" in fields and fields["location_type"] is not None:
            ltype = str(fields["location_type"]).upper()
            if ltype not in LOCATION_TYPES:
                raise CrmError("invalid_location_type", "Invalid location type")
            row.location_type = ltype
        if "status" in fields and fields["status"] is not None:
            stat = str(fields["status"]).upper()
            if stat not in LOCATION_STATUSES:
                raise CrmError("invalid_location_status", "Invalid location status")
            row.status = stat
        if fields.get("is_default") is True:
            self._clear_default(tenant_id)
            row.is_default = True
        if "address_metadata" in fields and fields["address_metadata"] is not None:
            row.address_metadata = dict(fields["address_metadata"])
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="inventory.location.update",
            resource_ids={"location_id": str(row.id)},
        )
        return serialize_location(row)

    def archive(self, tenant_id: UUID, location_id: UUID, *, actor: str) -> dict[str, Any]:
        row = self.get_row(tenant_id, location_id)
        active_stock = self._session.scalar(
            select(func.count())
            .select_from(InventoryBalance)
            .where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.location_id == location_id,
                InventoryBalance.stock_quantity > 0,
            )
        )
        if active_stock and int(active_stock) > 0:
            raise CrmError(
                "location_has_stock",
                "Cannot archive a location with stock on hand",
            )
        reserved = self._session.scalar(
            select(func.count())
            .select_from(InventoryBalance)
            .where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.location_id == location_id,
                InventoryBalance.reserved_quantity > 0,
            )
        )
        if reserved and int(reserved) > 0:
            raise CrmError(
                "location_has_reservations",
                "Cannot archive a location with active reservations",
            )
        row.archived_at = datetime.now(UTC)
        row.status = "INACTIVE"
        if row.is_default:
            row.is_default = False
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="inventory.location.archive",
            resource_ids={"location_id": str(row.id)},
        )
        return serialize_location(row)

    def restore(self, tenant_id: UUID, location_id: UUID, *, actor: str) -> dict[str, Any]:
        row = self._session.scalar(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == tenant_id,
                InventoryLocation.id == location_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Inventory location not found")
        row.archived_at = None
        row.status = "ACTIVE"
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="inventory.location.restore",
            resource_ids={"location_id": str(row.id)},
        )
        return serialize_location(row)

    def _clear_default(self, tenant_id: UUID) -> None:
        for loc in self._session.scalars(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == tenant_id,
                InventoryLocation.is_default.is_(True),
            )
        ):
            loc.is_default = False

"""Equipment CRUD facade (Phase 21)."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.equipment.attachments import EquipmentAttachmentService
from callbot_platform.crm.equipment.constants import (
    SELECTABLE_STATUSES,
    VALID_STATUS_TRANSITIONS,
    EquipmentStatus,
)
from callbot_platform.crm.equipment.history import EquipmentHistoryService
from callbot_platform.crm.equipment.search import EquipmentSearchService
from callbot_platform.crm.equipment.serialize import serialize_equipment
from callbot_platform.crm.equipment.warranty import EquipmentWarrantyService
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer, CustomerLocation
from callbot_platform.db.models.equipment import Equipment
from callbot_platform.db.models.jobs import Job
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


def normalize_serial(value: str | None) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    display = value.strip()
    if not display:
        return None, None
    return display[:128], display.upper()[:128]


def _parse_date(value: object | None, *, field: str) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise CrmError("invalid_date", f"Invalid {field}") from exc
    raise CrmError("invalid_date", f"Invalid {field}")


class EquipmentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = EquipmentSearchService(session)
        self.attachments = EquipmentAttachmentService(session)
        self.history = EquipmentHistoryService(session)
        self.warranty = EquipmentWarrantyService()

    def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _require_location(
        self, tenant_id: UUID, customer_id: UUID, location_id: UUID
    ) -> CustomerLocation:
        row = self._session.scalar(
            select(CustomerLocation).where(
                CustomerLocation.id == location_id,
                CustomerLocation.tenant_id == tenant_id,
            )
        )
        if row is None or row.archived_at is not None:
            raise CrmError("location_not_found", "Location not found for tenant")
        if row.customer_id != customer_id:
            raise CrmError(
                "location_customer_mismatch",
                "Location does not belong to the equipment customer",
            )
        return row

    def _load(
        self,
        tenant_id: UUID,
        equipment_id: UUID,
        *,
        for_update: bool = False,
        include_attachments: bool = False,
    ) -> Equipment:
        q = select(Equipment).where(
            Equipment.id == equipment_id, Equipment.tenant_id == tenant_id
        )
        if for_update:
            q = q.with_for_update()
        if include_attachments:
            q = q.options(selectinload(Equipment.attachments))
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Equipment not found for tenant")
        return row

    def _assert_serial_available(
        self, tenant_id: UUID, serial_norm: str | None, *, exclude_id: UUID | None = None
    ) -> None:
        if not serial_norm:
            return
        q = select(Equipment.id).where(
            Equipment.tenant_id == tenant_id,
            Equipment.serial_number_normalized == serial_norm,
        )
        if exclude_id is not None:
            q = q.where(Equipment.id != exclude_id)
        if self._session.scalar(q) is not None:
            raise CrmError(
                "serial_conflict",
                "An equipment record with this serial number already exists",
            )

    def _validate_dates(
        self,
        *,
        installation_date: date | None,
        warranty_start: date | None,
        warranty_end: date | None,
    ) -> None:
        today = datetime.now(UTC).date()
        if installation_date is not None and installation_date > today:
            raise CrmError(
                "invalid_installation_date",
                "installation_date cannot be in the future",
            )
        if (
            warranty_start is not None
            and warranty_end is not None
            and warranty_end < warranty_start
        ):
            raise CrmError(
                "invalid_warranty_dates",
                "warranty_end_date must be on or after warranty_start_date",
            )
        if (
            installation_date is not None
            and warranty_start is not None
            and warranty_start < installation_date
        ):
            raise CrmError(
                "invalid_warranty_dates",
                "warranty_start_date cannot be before installation_date",
            )

    def get(self, tenant_id: UUID, equipment_id: UUID) -> dict[str, Any]:
        row = self._load(tenant_id, equipment_id, include_attachments=True)
        urls: dict[str, str | None] = {}
        for att in row.attachments or []:
            if att.archived_at is None:
                urls[str(att.id)] = self.attachments._storage.create_download_url(
                    tenant_id=tenant_id, object_key=att.object_key
                )
        return serialize_equipment(
            row, include_attachments=True, attachment_urls=urls
        )

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        manufacturer: str,
        model: str,
        actor: str,
        location_id: UUID | None = None,
        serial_number: str | None = None,
        installation_date: object | None = None,
        warranty_start_date: object | None = None,
        warranty_end_date: object | None = None,
        warranty_provider: str | None = None,
        warranty_notes: str | None = None,
        status: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        customer = self._require_customer(tenant_id, customer_id)
        mfr = (manufacturer or "").strip()
        mdl = (model or "").strip()
        if not mfr or not mdl:
            raise CrmError(
                "invalid_identity",
                "manufacturer and model are required",
            )
        if location_id is not None:
            self._require_location(tenant_id, customer.id, location_id)
        serial_disp, serial_norm = normalize_serial(serial_number)
        self._assert_serial_available(tenant_id, serial_norm)
        install = _parse_date(installation_date, field="installation_date")
        w_start = _parse_date(warranty_start_date, field="warranty_start_date")
        w_end = _parse_date(warranty_end_date, field="warranty_end_date")
        self._validate_dates(
            installation_date=install, warranty_start=w_start, warranty_end=w_end
        )
        initial = (status or EquipmentStatus.ACTIVE.value).strip().upper()
        if initial not in {s.value for s in EquipmentStatus}:
            raise CrmError("invalid_status", f"Invalid status: {initial}")

        row = Equipment(
            tenant_id=tenant_id,
            customer_id=customer.id,
            location_id=location_id,
            manufacturer=mfr[:255],
            model=mdl[:255],
            serial_number=serial_disp,
            serial_number_normalized=serial_norm,
            installation_date=install,
            warranty_start_date=w_start,
            warranty_end_date=w_end,
            warranty_provider=(
                warranty_provider.strip()[:255]
                if warranty_provider and warranty_provider.strip()
                else None
            ),
            warranty_notes=(
                warranty_notes.strip()
                if warranty_notes and warranty_notes.strip()
                else None
            ),
            status=initial,
            notes=notes.strip() if notes and notes.strip() else None,
            metadata_json={},
            created_by=actor,
            updated_by=actor,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "serial_conflict",
                "An equipment record with this serial number already exists",
            ) from exc

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="equipment.created",
            resource_ids={
                "equipment_id": str(row.id),
                "customer_id": str(customer.id),
            },
            payload_summary={
                "manufacturer": row.manufacturer,
                "model": row.model,
                "serial_number": row.serial_number,
            },
        )
        logger.info(
            "equipment.created tenant_id=%s equipment_id=%s",
            tenant_id,
            row.id,
        )
        return self.get(tenant_id, row.id)

    def update(
        self,
        tenant_id: UUID,
        equipment_id: UUID,
        *,
        actor: str,
        manufacturer: str | None = None,
        model: str | None = None,
        serial_number: object = ...,
        location_id: object = ...,
        clear_location: bool = False,
        installation_date: object = ...,
        warranty_start_date: object = ...,
        warranty_end_date: object = ...,
        warranty_provider: object = ...,
        warranty_notes: object = ...,
        status: str | None = None,
        notes: object = ...,
    ) -> dict[str, Any]:
        row = self._load(tenant_id, equipment_id, for_update=True)
        if row.status == EquipmentStatus.REMOVED.value:
            raise CrmError("equipment_removed", "Removed equipment cannot be edited")

        if manufacturer is not None:
            mfr = manufacturer.strip()
            if not mfr:
                raise CrmError("invalid_identity", "manufacturer is required")
            row.manufacturer = mfr[:255]
        if model is not None:
            mdl = model.strip()
            if not mdl:
                raise CrmError("invalid_identity", "model is required")
            row.model = mdl[:255]

        if serial_number is not ...:
            disp, norm = normalize_serial(
                str(serial_number) if serial_number is not None else None
            )
            self._assert_serial_available(
                tenant_id, norm, exclude_id=row.id
            )
            row.serial_number = disp
            row.serial_number_normalized = norm

        if clear_location:
            row.location_id = None
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="equipment.location_changed",
                resource_ids={"equipment_id": str(row.id), "location_id": None},
            )
        elif location_id is not ... and location_id is not None:
            self._require_location(tenant_id, row.customer_id, UUID(str(location_id)))
            row.location_id = UUID(str(location_id))
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="equipment.location_changed",
                resource_ids={
                    "equipment_id": str(row.id),
                    "location_id": str(row.location_id),
                },
            )

        install = row.installation_date
        w_start = row.warranty_start_date
        w_end = row.warranty_end_date
        warranty_changed = False
        if installation_date is not ...:
            install = _parse_date(installation_date, field="installation_date")
            row.installation_date = install
        if warranty_start_date is not ...:
            w_start = _parse_date(warranty_start_date, field="warranty_start_date")
            row.warranty_start_date = w_start
            warranty_changed = True
        if warranty_end_date is not ...:
            w_end = _parse_date(warranty_end_date, field="warranty_end_date")
            row.warranty_end_date = w_end
            warranty_changed = True
        if warranty_provider is not ...:
            row.warranty_provider = (
                str(warranty_provider).strip()[:255]
                if warranty_provider and str(warranty_provider).strip()
                else None
            )
            warranty_changed = True
        if warranty_notes is not ...:
            row.warranty_notes = (
                str(warranty_notes).strip()
                if warranty_notes and str(warranty_notes).strip()
                else None
            )
            warranty_changed = True
        self._validate_dates(
            installation_date=install, warranty_start=w_start, warranty_end=w_end
        )
        if warranty_changed:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="equipment.warranty_changed",
                resource_ids={"equipment_id": str(row.id)},
            )

        if status is not None:
            target = status.strip().upper()
            if target not in {s.value for s in EquipmentStatus}:
                raise CrmError("invalid_status", f"Invalid status: {status}")
            if target != row.status:
                allowed = VALID_STATUS_TRANSITIONS.get(row.status, frozenset())
                if target not in allowed:
                    raise CrmError(
                        "invalid_status_transition",
                        f"Cannot transition from {row.status} to {target}",
                    )
                from_status = row.status
                row.status = target
                if target == EquipmentStatus.REMOVED.value:
                    row.archived_at = datetime.now(UTC)
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action="equipment.status_changed",
                    resource_ids={
                        "equipment_id": str(row.id),
                        "from_status": from_status,
                        "to_status": target,
                    },
                )

        if notes is not ...:
            row.notes = (
                str(notes).strip() if notes and str(notes).strip() else None
            )

        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "serial_conflict",
                "An equipment record with this serial number already exists",
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="equipment.updated",
            resource_ids={"equipment_id": str(row.id)},
        )
        return self.get(tenant_id, row.id)

    def archive(
        self, tenant_id: UUID, equipment_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        """Prefer RETIRED/REMOVED over physical delete when history exists."""
        row = self._load(tenant_id, equipment_id, for_update=True)
        job_count = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.tenant_id == tenant_id, Job.equipment_id == equipment_id)
        )
        from_status = row.status
        new_status = (
            EquipmentStatus.REMOVED.value
            if int(job_count or 0) > 0
            else EquipmentStatus.RETIRED.value
        )
        if row.status != new_status:
            row.status = new_status
            row.archived_at = datetime.now(UTC)
            row.updated_by = actor
            row.updated_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="equipment.archived",
                resource_ids={
                    "equipment_id": str(row.id),
                    "from_status": from_status,
                    "to_status": row.status,
                    "job_count": int(job_count or 0),
                },
            )
        return self.get(tenant_id, row.id)

    def delete(
        self, tenant_id: UUID, equipment_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        """Safe delete: archive when jobs exist; hard-delete only when unused."""
        row = self._load(tenant_id, equipment_id, for_update=True)
        job_count = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.tenant_id == tenant_id, Job.equipment_id == equipment_id)
        )
        if int(job_count or 0) > 0:
            return self.archive(tenant_id, equipment_id, actor=actor)
        eid = row.id
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="equipment.archived",
            resource_ids={"equipment_id": str(eid), "hard_deleted": True},
        )
        return {"id": str(eid), "deleted": True}

    @staticmethod
    def is_selectable(equipment: Equipment) -> bool:
        return (
            equipment.archived_at is None
            and equipment.status in SELECTABLE_STATUSES
        )

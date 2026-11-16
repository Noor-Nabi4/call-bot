"""Serialize equipment rows."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.equipment.warranty import EquipmentWarrantyService
from callbot_platform.db.models.equipment import Equipment, EquipmentAttachment


def serialize_attachment(
    row: EquipmentAttachment, *, download_url: str | None = None
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "equipment_id": str(row.equipment_id),
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": int(row.size_bytes),
        "kind": row.kind,
        "created_by": row.created_by,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "download_url": download_url,
    }


def serialize_equipment(
    row: Equipment,
    *,
    include_warranty: bool = True,
    include_attachments: bool = False,
    attachment_urls: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "customer_id": str(row.customer_id),
        "location_id": str(row.location_id) if row.location_id else None,
        "manufacturer": row.manufacturer,
        "model": row.model,
        "serial_number": row.serial_number,
        "installation_date": (
            row.installation_date.isoformat() if row.installation_date else None
        ),
        "warranty_start_date": (
            row.warranty_start_date.isoformat() if row.warranty_start_date else None
        ),
        "warranty_end_date": (
            row.warranty_end_date.isoformat() if row.warranty_end_date else None
        ),
        "warranty_provider": row.warranty_provider,
        "warranty_notes": row.warranty_notes,
        "status": row.status,
        "notes": row.notes,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_warranty:
        payload.update(EquipmentWarrantyService.summary(row))
    if include_attachments:
        urls = attachment_urls or {}
        payload["attachments"] = [
            serialize_attachment(a, download_url=urls.get(str(a.id)))
            for a in (row.attachments or [])
            if a.archived_at is None
        ]
    return payload

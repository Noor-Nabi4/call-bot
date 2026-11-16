"""Equipment attachment metadata + object storage (Phase 21)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.equipment.constants import (
    ATTACHMENT_MAX_BYTES,
    AttachmentKind,
)
from callbot_platform.crm.equipment.serialize import serialize_attachment
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.equipment import Equipment, EquipmentAttachment
from callbot_platform.storage import get_object_storage
from callbot_platform.storage.base import validate_object_mime_type
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_EXT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _sniff(data: bytes) -> str | None:
    if len(data) >= 5 and data[0:5] == b"%PDF-":
        return "application/pdf"
    if len(data) >= 3 and data[0:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 4 and data[0:4] == b"\x89PNG":
        return "image/png"
    if len(data) >= 4 and data[0:4] == b"GIF8":
        return "image/gif"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class EquipmentAttachmentService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._storage = get_object_storage(self._settings)

    def _equipment(self, tenant_id: UUID, equipment_id: UUID) -> Equipment:
        row = self._session.scalar(
            select(Equipment).where(
                Equipment.id == equipment_id, Equipment.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("not_found", "Equipment not found for tenant")
        return row

    def list(
        self, tenant_id: UUID, equipment_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        self._equipment(tenant_id, equipment_id)
        q = select(EquipmentAttachment).where(
            EquipmentAttachment.tenant_id == tenant_id,
            EquipmentAttachment.equipment_id == equipment_id,
        )
        if not include_archived:
            q = q.where(EquipmentAttachment.archived_at.is_(None))
        q = q.order_by(EquipmentAttachment.created_at.asc())
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            url = None
            if row.archived_at is None:
                url = self._storage.create_download_url(
                    tenant_id=tenant_id, object_key=row.object_key
                )
            out.append(serialize_attachment(row, download_url=url))
        return out

    def upload(
        self,
        tenant_id: UUID,
        equipment_id: UUID,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        actor: str,
        kind: str = AttachmentKind.PHOTO.value,
    ) -> dict[str, Any]:
        self._equipment(tenant_id, equipment_id)
        if not data:
            raise CrmError("invalid_attachment", "Empty file")
        if len(data) > ATTACHMENT_MAX_BYTES:
            raise CrmError("invalid_attachment", "File exceeds size limit")
        kind_u = (kind or AttachmentKind.PHOTO.value).strip().upper()
        if kind_u not in {k.value for k in AttachmentKind}:
            raise CrmError("invalid_attachment_kind", "Unsupported attachment kind")
        sniffed = _sniff(data)
        declared = (content_type or "").split(";")[0].strip().lower()
        if sniffed and sniffed != declared:
            raise CrmError("invalid_attachment", "Content type mismatch")
        mime = sniffed or declared
        try:
            validate_object_mime_type(mime)
        except Exception as exc:
            raise CrmError("invalid_attachment", "Unsupported content type") from exc
        if mime not in _EXT:
            raise CrmError("invalid_attachment", "Unsupported content type")
        ext = _EXT[mime]
        safe_name = (filename or f"file.{ext}").strip()[:255] or f"file.{ext}"
        object_key = f"equipment/{equipment_id}/attachments/{uuid.uuid4()}.{ext}"
        self._storage.put(
            tenant_id=tenant_id,
            object_key=object_key,
            data=data,
            mime_type=mime,
        )
        row = EquipmentAttachment(
            tenant_id=tenant_id,
            equipment_id=equipment_id,
            object_key=object_key,
            filename=safe_name,
            content_type=mime,
            size_bytes=len(data),
            kind=kind_u,
            created_by=actor,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="equipment.attachment_added",
            resource_ids={
                "equipment_id": str(equipment_id),
                "attachment_id": str(row.id),
            },
        )
        url = self._storage.create_download_url(
            tenant_id=tenant_id, object_key=object_key
        )
        return serialize_attachment(row, download_url=url)

    def archive(
        self,
        tenant_id: UUID,
        equipment_id: UUID,
        attachment_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        self._equipment(tenant_id, equipment_id)
        row = self._session.scalar(
            select(EquipmentAttachment).where(
                EquipmentAttachment.id == attachment_id,
                EquipmentAttachment.tenant_id == tenant_id,
                EquipmentAttachment.equipment_id == equipment_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Attachment not found for tenant")
        if row.archived_at is None:
            row.archived_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="equipment.attachment_removed",
                resource_ids={
                    "equipment_id": str(equipment_id),
                    "attachment_id": str(row.id),
                },
            )
        return serialize_attachment(row)

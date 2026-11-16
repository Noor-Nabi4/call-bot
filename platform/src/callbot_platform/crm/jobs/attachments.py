"""Job attachment metadata + object storage."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import ATTACHMENT_MAX_BYTES
from callbot_platform.crm.jobs.serialize import serialize_attachment
from callbot_platform.db.models.jobs import Job, JobAttachment
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
    "text/plain": "txt",
}

# MIME types that require magic-byte / content sniffing against the declared type.
_SNIFFED_TYPES = frozenset(_EXT.keys())


def _sniff_attachment_mime(data: bytes) -> str | None:
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
    # text/plain: reject obvious binary; allow UTF-8 / ASCII printable content
    sample = data[:4096]
    if b"\x00" in sample:
        return None
    try:
        sample.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return "text/plain"


class JobAttachmentService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._storage = get_object_storage(self._settings)

    def _job(self, tenant_id: UUID, job_id: UUID) -> Job:
        job = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        if job.archived_at is not None:
            raise CrmError("job_archived", "Job is archived")
        return job

    def _best_effort_delete_object(self, tenant_id: UUID, object_key: str) -> None:
        try:
            self._storage.delete(tenant_id=tenant_id, object_key=object_key)
        except Exception:
            logger.exception(
                "job_attachment_storage_cleanup_failed",
                extra={"tenant_id": str(tenant_id), "object_key": object_key},
            )

    def list(
        self, tenant_id: UUID, job_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        self._job(tenant_id, job_id)
        q = select(JobAttachment).where(
            JobAttachment.tenant_id == tenant_id, JobAttachment.job_id == job_id
        )
        if not include_archived:
            q = q.where(JobAttachment.archived_at.is_(None))
        q = q.order_by(JobAttachment.created_at.asc(), JobAttachment.id.asc())
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
        job_id: UUID,
        *,
        filename: str,
        content_type: str,
        data: bytes,
        actor: str,
    ) -> dict[str, Any]:
        self._job(tenant_id, job_id)
        if not data:
            raise CrmError("invalid_attachment", "Empty file")
        if len(data) > ATTACHMENT_MAX_BYTES:
            raise CrmError("invalid_attachment", "File exceeds size limit")
        try:
            mime = validate_object_mime_type(content_type)
        except ValueError as exc:
            raise CrmError("invalid_content_type", str(exc)) from exc

        if mime not in _SNIFFED_TYPES:
            raise CrmError(
                "invalid_content_type",
                f"Unsupported job attachment type: {mime}",
            )
        sniffed = _sniff_attachment_mime(data)
        if sniffed is None or sniffed != mime:
            raise CrmError(
                "invalid_content_type",
                "Attachment content type does not match file contents",
            )

        # Server-generated key only — never trust client paths.
        name = (filename or "attachment").strip().replace("\\", "/").split("/")[-1]
        name = name[:255] or "attachment"
        ext = _EXT.get(mime, "bin")
        object_key = f"jobs/{job_id}/attachments/{uuid.uuid4().hex}.{ext}"

        try:
            stored = self._storage.put(
                tenant_id=tenant_id,
                object_key=object_key,
                data=data,
                mime_type=mime,
            )
        except ValueError as exc:
            msg = str(exc)
            if "object_too_large" in msg:
                raise CrmError("invalid_attachment", "File exceeds size limit") from exc
            if "unsupported" in msg:
                raise CrmError("invalid_content_type", str(exc)) from exc
            raise CrmError("invalid_attachment", "Failed to store attachment") from exc

        row = JobAttachment(
            tenant_id=tenant_id,
            job_id=job_id,
            object_key=stored.object_key,
            filename=name,
            content_type=mime,
            size_bytes=stored.size_bytes,
            created_by=actor,
        )
        try:
            self._session.add(row)
            self._session.flush()
        except Exception:
            # Storage write succeeded; DB write failed — best-effort orphan cleanup.
            # Residual orphan risk remains if delete also fails (logged).
            self._best_effort_delete_object(tenant_id, stored.object_key)
            raise

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_attachment_added",
            resource_ids={"job_id": str(job_id), "attachment_id": str(row.id)},
        )
        url = self._storage.create_download_url(
            tenant_id=tenant_id, object_key=row.object_key
        )
        return serialize_attachment(row, download_url=url)

    def archive(
        self,
        tenant_id: UUID,
        job_id: UUID,
        attachment_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        self._job(tenant_id, job_id)
        row = self._session.scalar(
            select(JobAttachment).where(
                JobAttachment.id == attachment_id,
                JobAttachment.tenant_id == tenant_id,
                JobAttachment.job_id == job_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Attachment not found")
        if row.archived_at is None:
            row.archived_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="job_attachment_archived",
                resource_ids={
                    "job_id": str(job_id),
                    "attachment_id": str(row.id),
                },
            )
        return serialize_attachment(row)

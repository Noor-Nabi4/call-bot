"""Object storage abstraction for recordings and large files."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.recordings import RecordingObject
from callbot_platform.storage.base import (
    ObjectStorage,
    StoredObject,
    validate_object_mime_type,
)

logger = logging.getLogger(__name__)

__all__ = [
    "FilesystemObjectStorage",
    "ObjectStorage",
    "RecordingStorageService",
    "StoredObject",
    "get_object_storage",
]


class FilesystemObjectStorage(ObjectStorage):
    """Local filesystem backend for development and single-node deploys."""

    def __init__(self, root: str, *, max_upload_bytes: int = 52_428_800) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_bytes = int(max_upload_bytes)

    def _path(self, tenant_id: UUID, object_key: str) -> Path:
        safe_key = object_key.lstrip("/").replace("..", "")
        path = (self._root / str(tenant_id) / safe_key).resolve()
        if not str(path).startswith(str(self._root / str(tenant_id))):
            raise ValueError("invalid_object_key")
        return path

    def put(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        data: bytes,
        mime_type: str,
    ) -> StoredObject:
        if len(data) > self._max_bytes:
            raise ValueError("object_too_large")
        mime = validate_object_mime_type(mime_type)
        path = self._path(tenant_id, object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            object_key=object_key,
            size_bytes=len(data),
            mime_type=mime,
            backend="filesystem",
        )

    def get(self, *, tenant_id: UUID, object_key: str) -> bytes:
        return self._path(tenant_id, object_key).read_bytes()

    def delete(self, *, tenant_id: UUID, object_key: str) -> None:
        path = self._path(tenant_id, object_key)
        if path.exists():
            path.unlink()

    def exists(self, *, tenant_id: UUID, object_key: str) -> bool:
        return self._path(tenant_id, object_key).exists()

    def create_download_url(
        self, *, tenant_id: UUID, object_key: str, ttl_seconds: int = 300
    ) -> str:
        path = self._path(tenant_id, object_key)
        return f"file://{path}?ttl={ttl_seconds}"


def get_object_storage(settings: Settings | None = None) -> ObjectStorage:
    cfg = settings or get_settings()
    backend = (cfg.object_storage_backend or "filesystem").strip().lower()
    if backend == "filesystem":
        return FilesystemObjectStorage(
            cfg.object_storage_root,
            max_upload_bytes=cfg.object_storage_max_upload_bytes,
        )
    if backend in {"s3", "r2", "minio"}:
        from callbot_platform.storage.s3 import S3ObjectStorage

        return S3ObjectStorage(cfg)
    raise ValueError(f"Unsupported OBJECT_STORAGE_BACKEND={backend!r}")


class RecordingStorageService:
    """Persist recording metadata in DB; binaries in ObjectStorage."""

    def __init__(
        self,
        session: Session,
        storage: ObjectStorage | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._storage = storage or get_object_storage(self._settings)

    def store_recording(
        self,
        *,
        tenant_id: UUID,
        data: bytes,
        mime_type: str = "audio/wav",
        call_id: UUID | None = None,
        retention_days: int | None = None,
        object_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        key = object_key or f"recordings/{call_id or uuid.uuid4()}/{uuid.uuid4().hex}"
        stored = self._storage.put(
            tenant_id=tenant_id,
            object_key=key,
            data=data,
            mime_type=mime_type,
        )
        days = retention_days
        if days is None:
            from callbot_platform.db.models import TenantRetentionSettings

            row = self._session.scalar(
                select(TenantRetentionSettings).where(
                    TenantRetentionSettings.tenant_id == tenant_id
                )
            )
            days = (
                row.recording_retention_days
                if row
                else int(self._settings.recording_retention_days)
            )
        retention_until = datetime.now(UTC) + timedelta(days=int(days))
        rec = RecordingObject(
            tenant_id=tenant_id,
            call_id=call_id,
            provider="internal",
            object_key=stored.object_key,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            storage_backend=stored.backend,
            status="READY",
            lifecycle_status="ACTIVE",
            recorded_at=datetime.now(UTC),
            retention_until=retention_until,
            metadata_json=metadata or {},
        )
        self._session.add(rec)
        self._session.flush()
        return {
            "id": str(rec.id),
            "tenant_id": str(tenant_id),
            "object_key": rec.object_key,
            "mime_type": rec.mime_type,
            "size_bytes": rec.size_bytes,
            "retention_until": rec.retention_until.isoformat()
            if rec.retention_until
            else None,
            "status": rec.status,
        }

    def delete_expired(self, *, limit: int = 100) -> int:
        """Delete objects past retention_until; mark missing objects as deleted."""
        now = datetime.now(UTC)
        rows = list(
            self._session.scalars(
                select(RecordingObject)
                .where(
                    RecordingObject.lifecycle_status == "ACTIVE",
                    RecordingObject.retention_until.is_not(None),
                    RecordingObject.retention_until <= now,
                    RecordingObject.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        deleted = 0
        for row in rows:
            try:
                if self._storage.exists(
                    tenant_id=row.tenant_id, object_key=row.object_key
                ):
                    self._storage.delete(
                        tenant_id=row.tenant_id, object_key=row.object_key
                    )
                row.status = "DELETED"
                row.lifecycle_status = "DELETED"
                row.deleted_at = now
                row.updated_at = now
                deleted += 1
            except Exception:
                logger.exception(
                    "recording_delete_failed",
                    extra={
                        "tenant_id": str(row.tenant_id),
                        "recording_id": str(row.id),
                    },
                )
                row.status = "delete_failed"
                row.updated_at = now
        self._session.flush()
        return deleted

    def get_recording(
        self, tenant_id: UUID, recording_id: UUID
    ) -> dict[str, Any] | None:
        """Tenant-scoped recording metadata lookup (IDOR-safe)."""
        row = self._session.scalar(
            select(RecordingObject).where(
                RecordingObject.id == recording_id,
                RecordingObject.tenant_id == tenant_id,
                RecordingObject.deleted_at.is_(None),
            )
        )
        if row is None:
            return None
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "call_id": str(row.call_id) if row.call_id else None,
            "object_key": row.object_key,
            "mime_type": row.mime_type,
            "size_bytes": row.size_bytes,
            "status": row.status,
            "retention_until": row.retention_until.isoformat()
            if row.retention_until
            else None,
        }

    def presign_download(
        self,
        tenant_id: UUID,
        recording_id: UUID,
        *,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        """Issue a short-lived download URL only after tenant ownership is verified."""
        meta = self.get_recording(tenant_id, recording_id)
        if meta is None:
            return None
        ttl = int(
            ttl_seconds
            if ttl_seconds is not None
            else self._settings.object_storage_signed_url_ttl_seconds
        )
        url = self._storage.create_download_url(
            tenant_id=tenant_id,
            object_key=meta["object_key"],
            ttl_seconds=ttl,
        )
        return {**meta, "download_url": url, "ttl_seconds": ttl}

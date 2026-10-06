"""Object storage abstraction for recordings and large files."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.recordings import RecordingObject

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StoredObject:
    object_key: str
    size_bytes: int
    mime_type: str
    backend: str


class ObjectStorage(ABC):
    @abstractmethod
    def put(
        self,
        *,
        tenant_id: UUID,
        object_key: str,
        data: bytes,
        mime_type: str,
    ) -> StoredObject: ...

    @abstractmethod
    def get(self, *, tenant_id: UUID, object_key: str) -> bytes: ...

    @abstractmethod
    def delete(self, *, tenant_id: UUID, object_key: str) -> None: ...

    @abstractmethod
    def create_download_url(
        self, *, tenant_id: UUID, object_key: str, ttl_seconds: int = 300
    ) -> str: ...


class FilesystemObjectStorage(ObjectStorage):
    """Local filesystem backend for development and single-node deploys."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, tenant_id: UUID, object_key: str) -> Path:
        # Prevent path traversal outside tenant prefix.
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
        path = self._path(tenant_id, object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            object_key=object_key,
            size_bytes=len(data),
            mime_type=mime_type,
            backend="filesystem",
        )

    def get(self, *, tenant_id: UUID, object_key: str) -> bytes:
        path = self._path(tenant_id, object_key)
        return path.read_bytes()

    def delete(self, *, tenant_id: UUID, object_key: str) -> None:
        path = self._path(tenant_id, object_key)
        if path.exists():
            path.unlink()

    def create_download_url(
        self, *, tenant_id: UUID, object_key: str, ttl_seconds: int = 300
    ) -> str:
        # Local file URI — production should use signed S3 URLs via another backend.
        path = self._path(tenant_id, object_key)
        return f"file://{path}?ttl={ttl_seconds}"


def get_object_storage(settings: Settings | None = None) -> ObjectStorage:
    cfg = settings or get_settings()
    backend = (cfg.object_storage_backend or "filesystem").strip().lower()
    if backend == "filesystem":
        return FilesystemObjectStorage(cfg.object_storage_root)
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
            days = row.recording_retention_days if row else 30
        retention_until = datetime.now(UTC) + timedelta(days=int(days))
        rec = RecordingObject(
            tenant_id=tenant_id,
            call_id=call_id,
            object_key=stored.object_key,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            storage_backend=stored.backend,
            status="stored",
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
        """Delete objects past retention_until for their owning tenant only."""
        now = datetime.now(UTC)
        rows = list(
            self._session.scalars(
                select(RecordingObject)
                .where(
                    RecordingObject.status == "stored",
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
                self._storage.delete(tenant_id=row.tenant_id, object_key=row.object_key)
                row.status = "deleted"
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

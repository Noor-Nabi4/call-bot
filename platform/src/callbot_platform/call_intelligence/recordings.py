"""Call recording references + secure access (Phase 23)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.call_intelligence.constants import (
    LifecycleStatus,
    RecordingStatus,
)
from callbot_platform.call_intelligence.errors import CallIntelligenceError
from callbot_platform.call_intelligence.retention import (
    expires_at,
    load_retention_policy,
)
from callbot_platform.call_intelligence.serialize import serialize_recording
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.crm import Call
from callbot_platform.db.models.recordings import RecordingObject
from callbot_platform.storage import ObjectStorage, get_object_storage
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


def build_recording_storage_key(
    *,
    tenant_id: UUID,
    call_id: UUID,
    recording_id: UUID,
) -> str:
    """Server-authoritative tenant-scoped object key. Never trust client paths."""
    return f"tenants/{tenant_id}/calls/{call_id}/recordings/{recording_id}/audio"


class CallRecordingService:
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

    def _require_call(self, tenant_id: UUID, call_id: UUID) -> Call:
        row = self._session.scalar(
            select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
        )
        if row is None:
            raise CallIntelligenceError("call_not_found", "Call not found for tenant")
        return row

    def ingest(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        data: bytes,
        mime_type: str = "audio/wav",
        provider: str = "internal",
        provider_recording_id: str | None = None,
        duration_ms: int | None = None,
        recorded_at: datetime | None = None,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Idempotent recording ingest by (tenant, provider, provider_recording_id)."""
        self._require_call(tenant_id, call_id)
        policy = load_retention_policy(
            self._session, tenant_id, settings=self._settings
        )
        if not policy.recording_enabled:
            raise CallIntelligenceError(
                "recording_disabled", "Recording disabled for tenant"
            )

        if provider_recording_id:
            existing = self._session.scalar(
                select(RecordingObject).where(
                    RecordingObject.tenant_id == tenant_id,
                    RecordingObject.provider == provider,
                    RecordingObject.provider_recording_id == provider_recording_id,
                )
            )
            if existing is not None:
                return serialize_recording(existing)

        recording_id = uuid.uuid4()
        object_key = build_recording_storage_key(
            tenant_id=tenant_id, call_id=call_id, recording_id=recording_id
        )
        checksum = hashlib.sha256(data).hexdigest()

        # Provider/network I/O outside long-lived DB mutation where possible:
        # put to storage first, then insert metadata.
        stored = self._storage.put(
            tenant_id=tenant_id,
            object_key=object_key,
            data=data,
            mime_type=mime_type,
        )

        retention = expires_at(policy.recording_retention_days)
        row = RecordingObject(
            id=recording_id,
            tenant_id=tenant_id,
            call_id=call_id,
            provider=provider.strip()[:64] or "internal",
            provider_recording_id=(
                provider_recording_id.strip()[:255] if provider_recording_id else None
            ),
            object_key=stored.object_key,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            duration_ms=duration_ms,
            checksum=checksum,
            storage_backend=stored.backend,
            status=RecordingStatus.READY.value,
            lifecycle_status=LifecycleStatus.ACTIVE.value,
            recorded_at=recorded_at or datetime.now(UTC),
            retention_until=retention,
            metadata_json=metadata or {},
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            # Concurrent duplicate provider event — return winner
            if provider_recording_id:
                again = self._session.scalar(
                    select(RecordingObject).where(
                        RecordingObject.tenant_id == tenant_id,
                        RecordingObject.provider == provider,
                        RecordingObject.provider_recording_id == provider_recording_id,
                    )
                )
                if again is not None:
                    return serialize_recording(again)
            raise CallIntelligenceError(
                "recording_conflict", "Recording already exists"
            ) from None

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="RECORDING_INGESTED",
            resource_ids={"call_id": str(call_id), "recording_id": str(row.id)},
            payload_summary={
                "provider": row.provider,
                "size_bytes": row.size_bytes,
                "status": row.status,
            },
        )
        return serialize_recording(row)

    def get_for_call(self, tenant_id: UUID, call_id: UUID) -> dict[str, Any] | None:
        self._require_call(tenant_id, call_id)
        row = self._session.scalar(
            select(RecordingObject)
            .where(
                RecordingObject.tenant_id == tenant_id,
                RecordingObject.call_id == call_id,
                RecordingObject.deleted_at.is_(None),
                RecordingObject.lifecycle_status != LifecycleStatus.DELETED.value,
            )
            .order_by(RecordingObject.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return serialize_recording(row)

    def get(self, tenant_id: UUID, recording_id: UUID) -> RecordingObject | None:
        return self._session.scalar(
            select(RecordingObject).where(
                RecordingObject.id == recording_id,
                RecordingObject.tenant_id == tenant_id,
                RecordingObject.deleted_at.is_(None),
            )
        )

    def presign_download(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        actor: str,
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        self._require_call(tenant_id, call_id)
        row = self._session.scalar(
            select(RecordingObject)
            .where(
                RecordingObject.tenant_id == tenant_id,
                RecordingObject.call_id == call_id,
                RecordingObject.deleted_at.is_(None),
                RecordingObject.lifecycle_status == LifecycleStatus.ACTIVE.value,
                RecordingObject.status.in_(
                    [
                        RecordingStatus.READY.value,
                        RecordingStatus.AVAILABLE.value,
                        "stored",  # legacy
                    ]
                ),
            )
            .order_by(RecordingObject.created_at.desc())
            .limit(1)
        )
        if row is None:
            raise CallIntelligenceError(
                "recording_not_found", "Recording not available"
            )

        ttl = int(
            ttl_seconds
            if ttl_seconds is not None
            else self._settings.object_storage_signed_url_ttl_seconds
        )
        url = self._storage.create_download_url(
            tenant_id=tenant_id,
            object_key=row.object_key,
            ttl_seconds=ttl,
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="RECORDING_URL_GENERATED",
            resource_ids={"call_id": str(call_id), "recording_id": str(row.id)},
            payload_summary={"ttl_seconds": ttl},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="RECORDING_VIEWED",
            resource_ids={"call_id": str(call_id), "recording_id": str(row.id)},
            payload_summary={},
        )
        meta = serialize_recording(row)
        return {**meta, "download_url": url, "ttl_seconds": ttl}

    def mark_expired_and_delete_object(
        self, row: RecordingObject, *, actor: str = "system"
    ) -> None:
        """Idempotent storage delete + DB lifecycle update."""
        now = datetime.now(UTC)
        try:
            if self._storage.exists(tenant_id=row.tenant_id, object_key=row.object_key):
                self._storage.delete(tenant_id=row.tenant_id, object_key=row.object_key)
        except Exception:
            logger.exception(
                "recording_storage_delete_failed",
                extra={
                    "tenant_id": str(row.tenant_id),
                    "recording_id": str(row.id),
                },
            )
            # Object may already be gone — continue to DB update for idempotency
        row.status = RecordingStatus.DELETED.value
        row.lifecycle_status = LifecycleStatus.DELETED.value
        row.deleted_at = now
        row.updated_at = now
        write_audit(
            self._session,
            tenant_id=row.tenant_id,
            actor=actor,
            action="RECORDING_DELETED",
            resource_ids={
                "call_id": str(row.call_id) if row.call_id else None,
                "recording_id": str(row.id),
            },
            payload_summary={"reason": "retention"},
        )

    def cleanup_expired(self, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        rows = list(
            self._session.scalars(
                select(RecordingObject)
                .where(
                    RecordingObject.lifecycle_status == LifecycleStatus.ACTIVE.value,
                    RecordingObject.retention_until.is_not(None),
                    RecordingObject.retention_until <= now,
                    RecordingObject.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        # Mark EXPIRED first (do not delete immediately)
        for row in rows:
            row.lifecycle_status = LifecycleStatus.EXPIRED.value
            row.status = RecordingStatus.EXPIRED.value
            row.updated_at = now
        self._session.flush()

        expired = list(
            self._session.scalars(
                select(RecordingObject)
                .where(
                    RecordingObject.lifecycle_status == LifecycleStatus.EXPIRED.value,
                    RecordingObject.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        deleted = 0
        for row in expired:
            self.mark_expired_and_delete_object(row)
            deleted += 1
        self._session.flush()
        return deleted

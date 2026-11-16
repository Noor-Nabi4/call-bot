"""Transcript persistence and retrieval (Phase 23)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.call_intelligence.constants import (
    MAX_TRANSCRIBE_ATTEMPTS,
    LifecycleStatus,
    ProcessingStatus,
)
from callbot_platform.call_intelligence.errors import CallIntelligenceError
from callbot_platform.call_intelligence.providers import (
    TranscriptionProvider,
    get_transcription_provider,
)
from callbot_platform.call_intelligence.retention import (
    expires_at,
    load_retention_policy,
)
from callbot_platform.call_intelligence.serialize import serialize_transcript
from callbot_platform.call_intelligence.validation import (
    content_hash,
    normalize_segments,
)
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.call_intelligence import (
    CallTranscript,
    CallTranscriptSegment,
)
from callbot_platform.db.models.crm import Call
from callbot_platform.db.models.recordings import RecordingObject
from callbot_platform.storage import ObjectStorage, get_object_storage

logger = logging.getLogger(__name__)


class TranscriptService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        storage: ObjectStorage | None = None,
        provider: TranscriptionProvider | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._storage = storage or get_object_storage(self._settings)
        self._provider = provider or get_transcription_provider(self._settings)

    def _require_call(self, tenant_id: UUID, call_id: UUID) -> Call:
        row = self._session.scalar(
            select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
        )
        if row is None:
            raise CallIntelligenceError("call_not_found", "Call not found for tenant")
        return row

    def get_or_create_pending(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        recording_id: UUID,
        input_hash: str | None = None,
    ) -> CallTranscript:
        self._require_call(tenant_id, call_id)
        existing = self._session.scalar(
            select(CallTranscript).where(
                CallTranscript.tenant_id == tenant_id,
                CallTranscript.recording_id == recording_id,
                CallTranscript.deleted_at.is_(None),
                CallTranscript.status.in_(
                    [
                        ProcessingStatus.PENDING.value,
                        ProcessingStatus.PROCESSING.value,
                        ProcessingStatus.COMPLETED.value,
                    ]
                ),
            )
        )
        if existing is not None:
            return existing

        policy = load_retention_policy(
            self._session, tenant_id, settings=self._settings
        )
        row = CallTranscript(
            tenant_id=tenant_id,
            call_id=call_id,
            recording_id=recording_id,
            status=ProcessingStatus.PENDING.value,
            input_hash=input_hash,
            lifecycle_status=LifecycleStatus.ACTIVE.value,
            expires_at=expires_at(policy.transcript_retention_days),
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            again = self._session.scalar(
                select(CallTranscript).where(
                    CallTranscript.tenant_id == tenant_id,
                    CallTranscript.recording_id == recording_id,
                    CallTranscript.deleted_at.is_(None),
                )
            )
            if again is not None:
                return again
            raise
        return row

    def get_for_call(
        self,
        tenant_id: UUID,
        call_id: UUID,
        *,
        include_segments: bool = True,
    ) -> dict[str, Any] | None:
        self._require_call(tenant_id, call_id)
        row = self._session.scalar(
            select(CallTranscript)
            .where(
                CallTranscript.tenant_id == tenant_id,
                CallTranscript.call_id == call_id,
                CallTranscript.deleted_at.is_(None),
                CallTranscript.lifecycle_status != LifecycleStatus.DELETED.value,
            )
            .order_by(CallTranscript.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        segments = None
        if include_segments and row.status == ProcessingStatus.COMPLETED.value:
            segments = list(
                self._session.scalars(
                    select(CallTranscriptSegment)
                    .where(
                        CallTranscriptSegment.tenant_id == tenant_id,
                        CallTranscriptSegment.transcript_id == row.id,
                    )
                    .order_by(CallTranscriptSegment.sequence.asc())
                ).all()
            )
        return serialize_transcript(row, segments=segments)

    def process_recording(
        self,
        *,
        tenant_id: UUID,
        recording_id: UUID,
    ) -> dict[str, Any]:
        """Transcribe a recording. Idempotent for completed transcripts."""
        recording = self._session.scalar(
            select(RecordingObject).where(
                RecordingObject.id == recording_id,
                RecordingObject.tenant_id == tenant_id,
                RecordingObject.deleted_at.is_(None),
            )
        )
        if recording is None or recording.call_id is None:
            raise CallIntelligenceError(
                "recording_not_found", "Recording not found for tenant"
            )

        policy = load_retention_policy(
            self._session, tenant_id, settings=self._settings
        )
        if not policy.transcription_enabled:
            raise CallIntelligenceError(
                "transcription_disabled", "Transcription disabled for tenant"
            )

        input_hash = content_hash(
            str(recording.id),
            recording.checksum or "",
            str(recording.size_bytes),
        )
        transcript = self.get_or_create_pending(
            tenant_id=tenant_id,
            call_id=recording.call_id,
            recording_id=recording.id,
            input_hash=input_hash,
        )

        if transcript.status == ProcessingStatus.COMPLETED.value:
            return serialize_transcript(transcript)

        if transcript.attempt_count >= MAX_TRANSCRIBE_ATTEMPTS:
            transcript.status = ProcessingStatus.FAILED.value
            transcript.last_error = "max_attempts_exceeded"
            self._session.flush()
            return serialize_transcript(transcript)

        # Claim
        transcript.status = ProcessingStatus.PROCESSING.value
        transcript.attempt_count = int(transcript.attempt_count) + 1
        transcript.started_at = datetime.now(UTC)
        transcript.last_error = None
        self._session.flush()

        # Provider I/O outside holding locks beyond flush
        audio = self._storage.get(tenant_id=tenant_id, object_key=recording.object_key)
        result = self._provider.transcribe(
            audio_bytes=audio,
            mime_type=recording.mime_type,
        )
        segments = normalize_segments(result.segments)

        # Clear prior segments if reprocessing failed→retry
        existing_segs = list(
            self._session.scalars(
                select(CallTranscriptSegment).where(
                    CallTranscriptSegment.tenant_id == tenant_id,
                    CallTranscriptSegment.transcript_id == transcript.id,
                )
            ).all()
        )
        for seg in existing_segs:
            self._session.delete(seg)

        for seg in segments:
            self._session.add(
                CallTranscriptSegment(
                    tenant_id=tenant_id,
                    transcript_id=transcript.id,
                    speaker=seg["speaker"],
                    start_ms=seg["start_ms"],
                    end_ms=seg["end_ms"],
                    text=seg["text"],
                    confidence=seg["confidence"],
                    sequence=seg["sequence"],
                )
            )

        transcript.provider = result.provider
        transcript.provider_transcript_id = result.provider_transcript_id
        transcript.language = result.language
        transcript.full_text = result.full_text
        transcript.status = ProcessingStatus.COMPLETED.value
        transcript.completed_at = datetime.now(UTC)
        transcript.updated_at = datetime.now(UTC)
        self._session.flush()
        return serialize_transcript(transcript)

    def mark_failed(self, transcript: CallTranscript, error: str) -> None:
        transcript.status = ProcessingStatus.FAILED.value
        transcript.last_error = error[:2000]
        transcript.updated_at = datetime.now(UTC)
        self._session.flush()

    def cleanup_expired(self, *, limit: int = 100) -> int:
        now = datetime.now(UTC)
        rows = list(
            self._session.scalars(
                select(CallTranscript)
                .where(
                    CallTranscript.lifecycle_status == LifecycleStatus.ACTIVE.value,
                    CallTranscript.expires_at.is_not(None),
                    CallTranscript.expires_at <= now,
                    CallTranscript.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        for row in rows:
            row.lifecycle_status = LifecycleStatus.EXPIRED.value
            row.updated_at = now
        self._session.flush()

        expired = list(
            self._session.scalars(
                select(CallTranscript)
                .where(
                    CallTranscript.lifecycle_status == LifecycleStatus.EXPIRED.value,
                    CallTranscript.deleted_at.is_(None),
                )
                .limit(limit)
            ).all()
        )
        for row in expired:
            # Soft-delete transcript text; segments cascade on hard delete of row
            # but we keep row for audit — clear full_text
            row.full_text = ""
            row.lifecycle_status = LifecycleStatus.DELETED.value
            row.deleted_at = now
            row.updated_at = now
            segs = list(
                self._session.scalars(
                    select(CallTranscriptSegment).where(
                        CallTranscriptSegment.tenant_id == row.tenant_id,
                        CallTranscriptSegment.transcript_id == row.id,
                    )
                ).all()
            )
            for seg in segs:
                self._session.delete(seg)
        self._session.flush()
        return len(expired)

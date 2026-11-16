"""Call Intelligence pipeline: recording → transcript → analysis → automation events."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.async_jobs.service import AsyncJobService
from callbot_platform.async_jobs.types import JobType
from callbot_platform.automations.publishers import (
    publish_call_analyzed,
    publish_call_classified,
    publish_call_transcribed,
)
from callbot_platform.call_intelligence.analysis import AnalysisService
from callbot_platform.call_intelligence.errors import CallIntelligenceError
from callbot_platform.call_intelligence.recordings import CallRecordingService
from callbot_platform.call_intelligence.retention import load_retention_policy
from callbot_platform.call_intelligence.search import CallIntelligenceSearchService
from callbot_platform.call_intelligence.transcripts import TranscriptService
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models.call_intelligence import CallTranscript
from callbot_platform.storage import ObjectStorage

logger = logging.getLogger(__name__)


class CallIntelligenceService:
    """Facade for Call Intelligence APIs and async pipeline entry points."""

    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        storage: ObjectStorage | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self.recordings = CallRecordingService(
            session, storage=storage, settings=self._settings
        )
        self.transcripts = TranscriptService(
            session, settings=self._settings, storage=storage
        )
        self.analysis = AnalysisService(session, settings=self._settings)
        self.search = CallIntelligenceSearchService(session)
        self._jobs = AsyncJobService(session, settings=self._settings)

    def enqueue_transcribe(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        recording_id: UUID,
    ) -> dict[str, Any]:
        policy = load_retention_policy(
            self._session, tenant_id, settings=self._settings
        )
        if not policy.transcription_enabled:
            return {"enqueued": False, "reason": "transcription_disabled"}
        job = self._jobs.enqueue(
            tenant_id=tenant_id,
            job_type=JobType.CALL_TRANSCRIBE,
            idempotency_key=f"call-transcribe:{recording_id}",
            resource_id=str(recording_id),
            payload={
                "call_id": str(call_id),
                "recording_id": str(recording_id),
            },
            max_attempts=5,
        )
        return {"enqueued": True, "job_id": str(job.id), "status": job.status}

    def enqueue_analyze(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        transcript_id: UUID,
        force_new_version: bool = False,
    ) -> dict[str, Any]:
        key = (
            f"call-analyze:{transcript_id}:vforce"
            if force_new_version
            else f"call-analyze:{transcript_id}"
        )
        job = self._jobs.enqueue(
            tenant_id=tenant_id,
            job_type=JobType.CALL_ANALYZE,
            idempotency_key=key,
            resource_id=str(transcript_id),
            payload={
                "call_id": str(call_id),
                "transcript_id": str(transcript_id),
                "force_new_version": force_new_version,
            },
            max_attempts=5,
        )
        return {"enqueued": True, "job_id": str(job.id), "status": job.status}

    def on_recording_ready(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        recording_id: UUID,
    ) -> dict[str, Any]:
        return self.enqueue_transcribe(
            tenant_id=tenant_id, call_id=call_id, recording_id=recording_id
        )

    def run_transcribe_job(
        self, *, tenant_id: UUID, recording_id: UUID
    ) -> dict[str, Any]:
        result = self.transcripts.process_recording(
            tenant_id=tenant_id, recording_id=recording_id
        )
        if result.get("status") == "COMPLETED":
            call_id = UUID(str(result["call_id"]))
            transcript_id = UUID(str(result["id"]))
            publish_call_transcribed(
                self._session,
                tenant_id=tenant_id,
                call_id=call_id,
                transcript_id=transcript_id,
            )
            self.enqueue_analyze(
                tenant_id=tenant_id,
                call_id=call_id,
                transcript_id=transcript_id,
            )
        return result

    def run_analyze_job(
        self,
        *,
        tenant_id: UUID,
        transcript_id: UUID,
        force_new_version: bool = False,
    ) -> dict[str, Any]:
        result = self.analysis.analyze_transcript(
            tenant_id=tenant_id,
            transcript_id=transcript_id,
            force_new_version=force_new_version,
        )
        if result.get("analysis_status") == "COMPLETED":
            call_id = UUID(str(result["call_id"]))
            publish_call_analyzed(
                self._session,
                tenant_id=tenant_id,
                call_id=call_id,
                intelligence_id=UUID(str(result["id"])),
                classification=result.get("classification"),
                sentiment=result.get("sentiment"),
                intent=result.get("intent"),
            )
            publish_call_classified(
                self._session,
                tenant_id=tenant_id,
                call_id=call_id,
                classification=result.get("classification") or "OTHER",
                confidence=result.get("classification_confidence"),
                source=result.get("classification_source"),
            )
        return result

    def reanalyze(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID,
        actor: str,
    ) -> dict[str, Any]:
        from sqlalchemy import select

        transcript = self._session.scalar(
            select(CallTranscript)
            .where(
                CallTranscript.tenant_id == tenant_id,
                CallTranscript.call_id == call_id,
                CallTranscript.deleted_at.is_(None),
                CallTranscript.status == "COMPLETED",
            )
            .order_by(CallTranscript.created_at.desc())
            .limit(1)
        )
        if transcript is None:
            raise CallIntelligenceError(
                "transcript_not_found", "No completed transcript to reanalyze"
            )
        # Clear prior analyze job idempotency by forcing new version + new key
        return self.enqueue_analyze(
            tenant_id=tenant_id,
            call_id=call_id,
            transcript_id=transcript.id,
            force_new_version=True,
        )

    def cleanup_retention(self, *, limit: int = 100) -> dict[str, int]:
        return {
            "recordings": self.recordings.cleanup_expired(limit=limit),
            "transcripts": self.transcripts.cleanup_expired(limit=limit),
            "analysis": self.analysis.cleanup_expired(limit=limit),
        }

"""Async job handlers for Call Intelligence pipeline."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.call_intelligence import CallIntelligenceService
from callbot_platform.call_intelligence.errors import CallIntelligenceError
from callbot_platform.config import Settings
from callbot_platform.db.models.async_job import AsyncJob


class CallIntelligenceJobHandler:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def handle_transcribe(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        payload = dict(job.payload or {})
        recording_id = UUID(str(payload["recording_id"]))
        try:
            return CallIntelligenceService(
                session, settings=self._settings
            ).run_transcribe_job(tenant_id=job.tenant_id, recording_id=recording_id)
        except CallIntelligenceError as exc:
            if exc.code in {
                "recording_not_found",
                "transcription_disabled",
                "call_not_found",
            }:
                return {
                    "status": "FAILED",
                    "code": exc.code,
                    "message": str(exc)[:500],
                    "permanent": True,
                }
            raise

    def handle_analyze(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        payload = dict(job.payload or {})
        transcript_id = UUID(str(payload["transcript_id"]))
        force = bool(payload.get("force_new_version"))
        try:
            return CallIntelligenceService(
                session, settings=self._settings
            ).run_analyze_job(
                tenant_id=job.tenant_id,
                transcript_id=transcript_id,
                force_new_version=force,
            )
        except CallIntelligenceError as exc:
            if exc.code in {
                "transcript_not_found",
                "transcript_not_ready",
                "call_not_found",
            }:
                return {
                    "status": "FAILED",
                    "code": exc.code,
                    "message": str(exc)[:500],
                    "permanent": True,
                }
            raise

    def handle_retention(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        limit = int((job.payload or {}).get("limit") or 100)
        return CallIntelligenceService(
            session, settings=self._settings
        ).cleanup_retention(limit=limit)

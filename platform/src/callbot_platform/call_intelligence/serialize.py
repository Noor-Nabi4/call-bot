"""Serialize Call Intelligence entities for API responses."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.call_intelligence import (
    CallIntelligence,
    CallTranscript,
    CallTranscriptSegment,
)
from callbot_platform.db.models.recordings import RecordingObject


def serialize_recording(
    row: RecordingObject, *, include_key: bool = False
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "call_id": str(row.call_id) if row.call_id else None,
        "provider": row.provider,
        "provider_recording_id": row.provider_recording_id,
        "mime_type": row.mime_type,
        "size_bytes": row.size_bytes,
        "duration_ms": row.duration_ms,
        "checksum": row.checksum,
        "storage_provider": row.storage_backend,
        "status": row.status,
        "lifecycle_status": row.lifecycle_status,
        "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
        "expires_at": row.retention_until.isoformat() if row.retention_until else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_key:
        data["storage_key"] = row.object_key
    return data


def serialize_segment(row: CallTranscriptSegment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "speaker": row.speaker,
        "start_ms": row.start_ms,
        "end_ms": row.end_ms,
        "text": row.text,
        "confidence": row.confidence,
        "sequence": row.sequence,
    }


def serialize_transcript(
    row: CallTranscript,
    *,
    segments: list[CallTranscriptSegment] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "call_id": str(row.call_id),
        "recording_id": str(row.recording_id) if row.recording_id else None,
        "provider": row.provider,
        "provider_transcript_id": row.provider_transcript_id,
        "language": row.language,
        "status": row.status,
        "full_text": row.full_text if row.status == "COMPLETED" else None,
        "attempt_count": row.attempt_count,
        "last_error": row.last_error,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "lifecycle_status": row.lifecycle_status,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if segments is not None:
        data["segments"] = [serialize_segment(s) for s in segments]
    return data


def serialize_intelligence(row: CallIntelligence) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "call_id": str(row.call_id),
        "transcript_id": str(row.transcript_id) if row.transcript_id else None,
        "intent": row.intent,
        "problem": row.problem,
        "outcome": row.outcome,
        "sentiment": row.sentiment,
        "appointment_status": row.appointment_status,
        "follow_up": row.follow_up,
        "classification": row.classification,
        "classification_confidence": row.classification_confidence,
        "classification_source": row.classification_source,
        "important_notes": list(row.important_notes or []),
        "analysis_status": row.analysis_status,
        "provider": row.provider,
        "model": row.model,
        "model_version": row.model_version,
        "analysis_version": row.analysis_version,
        "attempt_count": row.attempt_count,
        "last_error": row.last_error,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "lifecycle_status": row.lifecycle_status,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }

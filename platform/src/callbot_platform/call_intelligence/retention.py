"""Retention settings and expiry helpers for Call Intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import TenantRetentionSettings


@dataclass(frozen=True)
class RetentionPolicy:
    recording_enabled: bool
    transcription_enabled: bool
    recording_retention_days: int
    transcript_retention_days: int
    analysis_retention_days: int


def load_retention_policy(
    session: Session,
    tenant_id: UUID,
    *,
    settings: Settings | None = None,
) -> RetentionPolicy:
    cfg = settings or get_settings()
    row = session.scalar(
        select(TenantRetentionSettings).where(
            TenantRetentionSettings.tenant_id == tenant_id
        )
    )
    if row is None:
        return RetentionPolicy(
            recording_enabled=True,
            transcription_enabled=True,
            recording_retention_days=int(cfg.recording_retention_days),
            transcript_retention_days=90,
            analysis_retention_days=90,
        )
    return RetentionPolicy(
        recording_enabled=bool(row.recording_enabled),
        transcription_enabled=bool(row.transcription_enabled),
        recording_retention_days=int(row.recording_retention_days),
        transcript_retention_days=int(row.transcript_retention_days),
        analysis_retention_days=int(row.analysis_retention_days),
    )


def expires_at(days: int, *, from_time: datetime | None = None) -> datetime:
    base = from_time or datetime.now(UTC)
    return base + timedelta(days=max(1, int(days)))

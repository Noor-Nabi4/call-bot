"""Call Intelligence models (Phase 23): transcripts, segments, analysis."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class CallTranscript(Base):
    __tablename__ = "call_transcripts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_call_transcripts_status",
        ),
        CheckConstraint(
            "lifecycle_status IN ('ACTIVE','EXPIRED','DELETED')",
            name="ck_call_transcripts_lifecycle",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_call_transcripts_attempts"),
        Index("ix_call_transcripts_tenant_call", "tenant_id", "call_id"),
        Index("ix_call_transcripts_tenant_status", "tenant_id", "status"),
        Index("ix_call_transcripts_tenant_created", "tenant_id", "created_at"),
        Index("ix_call_transcripts_tenant_lifecycle", "tenant_id", "lifecycle_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    recording_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recording_objects.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="internal")
    provider_transcript_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )


class CallTranscriptSegment(Base):
    __tablename__ = "call_transcript_segments"
    __table_args__ = (
        CheckConstraint(
            "speaker IN ('CUSTOMER','AGENT','SYSTEM','UNKNOWN')",
            name="ck_call_transcript_segments_speaker",
        ),
        CheckConstraint(
            "start_ms >= 0 AND end_ms >= start_ms AND sequence >= 0",
            name="ck_call_transcript_segments_timing",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_call_transcript_segments_confidence",
        ),
        UniqueConstraint(
            "tenant_id",
            "transcript_id",
            "sequence",
            name="uq_call_transcript_segments_seq",
        ),
        Index(
            "ix_call_transcript_segments_transcript_seq",
            "transcript_id",
            "sequence",
        ),
        Index(
            "ix_call_transcript_segments_tenant_speaker",
            "tenant_id",
            "speaker",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("call_transcripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


class CallIntelligence(Base):
    __tablename__ = "call_intelligence"
    __table_args__ = (
        CheckConstraint(
            "analysis_status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_call_intelligence_status",
        ),
        CheckConstraint(
            "lifecycle_status IN ('ACTIVE','EXPIRED','DELETED')",
            name="ck_call_intelligence_lifecycle",
        ),
        CheckConstraint(
            "sentiment IS NULL OR sentiment IN "
            "('POSITIVE','NEUTRAL','NEGATIVE','MIXED','UNKNOWN')",
            name="ck_call_intelligence_sentiment",
        ),
        CheckConstraint(
            "intent IS NULL OR intent IN ("
            "'BOOKING','RESCHEDULING','CANCELLATION','SALES','SUPPORT',"
            "'EMERGENCY','BILLING','PRODUCT_INQUIRY','ORDER_INQUIRY',"
            "'SPAM','HUMAN_TRANSFER','OTHER'"
            ")",
            name="ck_call_intelligence_intent",
        ),
        CheckConstraint(
            "classification IS NULL OR classification IN ("
            "'BOOKING','RESCHEDULING','CANCELLATION','SALES','SUPPORT',"
            "'EMERGENCY','BILLING','PRODUCT_INQUIRY','ORDER_INQUIRY',"
            "'SPAM','HUMAN_TRANSFER','OTHER'"
            ")",
            name="ck_call_intelligence_classification",
        ),
        CheckConstraint(
            "follow_up IS NULL OR follow_up IN ("
            "'CALL_BACK','SEND_INFORMATION','SEND_PAYMENT_LINK',"
            "'FOLLOW_UP_SALES','TECHNICIAN_FOLLOW_UP',"
            "'CUSTOMER_ACTION_REQUIRED','NONE'"
            ")",
            name="ck_call_intelligence_follow_up",
        ),
        CheckConstraint(
            "appointment_status IS NULL OR appointment_status IN ("
            "'NONE','REQUESTED','SCHEDULED','CONFIRMED','RESCHEDULED',"
            "'CANCELLED','COMPLETED','UNKNOWN'"
            ")",
            name="ck_call_intelligence_appt_status",
        ),
        CheckConstraint(
            "classification_confidence IS NULL OR "
            "(classification_confidence >= 0 AND classification_confidence <= 1)",
            name="ck_call_intelligence_confidence",
        ),
        CheckConstraint(
            "classification_source IS NULL OR "
            "classification_source IN ('RULE','AI','HYBRID')",
            name="ck_call_intelligence_class_source",
        ),
        CheckConstraint(
            "analysis_version >= 1 AND attempt_count >= 0",
            name="ck_call_intelligence_versions",
        ),
        UniqueConstraint(
            "tenant_id",
            "call_id",
            "analysis_version",
            name="uq_call_intelligence_tenant_call_version",
        ),
        Index("ix_call_intelligence_tenant_call", "tenant_id", "call_id"),
        Index("ix_call_intelligence_tenant_created", "tenant_id", "created_at"),
        Index(
            "ix_call_intelligence_tenant_classification",
            "tenant_id",
            "classification",
        ),
        Index("ix_call_intelligence_tenant_sentiment", "tenant_id", "sentiment"),
        Index("ix_call_intelligence_tenant_status", "tenant_id", "analysis_status"),
        Index(
            "ix_call_intelligence_tenant_lifecycle",
            "tenant_id",
            "lifecycle_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    transcript_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("call_transcripts.id", ondelete="SET NULL"),
        nullable=True,
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    appointment_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    follow_up: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    classification_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    important_notes: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    analysis_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

"""Per-call estimated COGS (internal; not customer billing)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow


class CallCogs(Base):
    __tablename__ = "call_cogs"
    __table_args__ = (
        Index("ix_call_cogs_tenant_id_created_at", "tenant_id", "created_at"),
    )

    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    billable_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    transfer_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none"
    )
    openai_cost_micros: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    livekit_agent_cost_micros: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    livekit_sip_cost_micros: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    livekit_bvc_cost_micros: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    twilio_origination_cost_micros: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    twilio_termination_cost_micros: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_estimated_cogs_micros: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    openai_cost_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="per_minute_estimate"
    )
    openai_usage: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    rate_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    notes: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
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

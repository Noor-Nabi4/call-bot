"""Handoff and retention ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid
from callbot_platform.db.models.tenant import Tenant


class TenantHandoffSettings(Base):
    __tablename__ = "tenant_handoff_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_handoff_settings_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="warm")
    escalation_phone_e164: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sip_outbound_trunk_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
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

    tenant: Mapped[Tenant] = relationship(back_populates="handoff_settings")


class TenantRetentionSettings(Base):
    __tablename__ = "tenant_retention_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_retention_settings_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    recording_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    transcript_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90
    )
    analysis_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=90
    )
    recording_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    transcription_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    audit_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365
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

    tenant: Mapped[Tenant] = relationship(back_populates="retention_settings")

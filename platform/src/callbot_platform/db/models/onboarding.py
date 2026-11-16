"""Organization onboarding workflow state (tenant-owned, 1:1)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class OrganizationOnboarding(Base):
    __tablename__ = "organization_onboarding"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_organization_onboarding_tenant_id"),
        Index("ix_organization_onboarding_tenant_id", "tenant_id"),
        Index("ix_organization_onboarding_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NOT_STARTED"
    )
    current_step: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_steps: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    skipped_steps: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_data: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
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

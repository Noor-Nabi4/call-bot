"""Recording object metadata (binaries live in object storage)."""

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


class RecordingObject(Base):
    __tablename__ = "recording_objects"
    __table_args__ = (
        Index("ix_recording_objects_tenant_id", "tenant_id"),
        Index(
            "ix_recording_objects_tenant_retention",
            "tenant_id",
            "retention_until",
        ),
        UniqueConstraint(
            "tenant_id", "object_key", name="uq_recording_objects_tenant_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_backend: Mapped[str] = mapped_column(
        String(32), nullable=False, default="filesystem"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="stored")
    retention_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

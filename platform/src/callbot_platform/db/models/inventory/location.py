"""Inventory locations (tenant-scoped stock sites)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code_normalized", name="uq_inventory_locations_code"),
        Index("ix_inventory_locations_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_inventory_locations_status",
        ),
        CheckConstraint(
            "location_type IN ('WAREHOUSE', 'STORE', 'OFFICE', 'VEHICLE', 'FIELD', 'OTHER')",
            name="ck_inventory_locations_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    code_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_type: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    address_metadata: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    archived_at: Mapped[datetime | None] = mapped_column(
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

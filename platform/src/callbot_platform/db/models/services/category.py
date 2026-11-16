"""Service category model (nested via parent_id)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.services.service import Service


class ServiceCategory(Base):
    __tablename__ = "service_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_service_categories_tenant_slug"),
        Index("ix_service_categories_tenant_id", "tenant_id"),
        Index("ix_service_categories_tenant_parent", "tenant_id", "parent_id"),
        Index("ix_service_categories_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_service_categories_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_service_categories_status",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_service_categories_no_self_parent",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
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

    parent: Mapped[ServiceCategory | None] = relationship(
        remote_side="ServiceCategory.id",
        back_populates="children",
    )
    children: Mapped[list[ServiceCategory]] = relationship(
        back_populates="parent",
    )
    services: Mapped[list[Service]] = relationship(back_populates="category")

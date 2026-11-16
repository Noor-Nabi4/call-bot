"""Tenant-scoped SKU registry spanning products and variants."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, _utcnow, _uuid


class CatalogSku(Base):
    """Ensures one active SKU identity per tenant across product and variant owners."""

    __tablename__ = "catalog_skus"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku_normalized", name="uq_catalog_skus_tenant"),
        Index("ix_catalog_skus_tenant_owner", "tenant_id", "owner_kind", "owner_id"),
        CheckConstraint(
            "owner_kind IN ('product', 'variant')",
            name="ck_catalog_skus_owner_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

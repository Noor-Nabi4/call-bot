"""Product image metadata (bytes live in object storage)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.catalog.product import Product
    from callbot_platform.db.models.catalog.variant import ProductVariant


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_tenant_product", "tenant_id", "product_id"),
        Index("ix_product_images_tenant_variant", "tenant_id", "variant_id"),
        UniqueConstraint(
            "tenant_id", "object_key", name="uq_product_images_tenant_key"
        ),
        Index(
            "uq_product_images_primary_product",
            "tenant_id",
            "product_id",
            unique=True,
            postgresql_where=text(
                "archived_at IS NULL AND is_primary IS TRUE AND variant_id IS NULL"
            ),
            sqlite_where=text(
                "archived_at IS NULL AND is_primary = 1 AND variant_id IS NULL"
            ),
        ),
        Index(
            "uq_product_images_primary_variant",
            "tenant_id",
            "variant_id",
            unique=True,
            postgresql_where=text(
                "archived_at IS NULL AND is_primary IS TRUE AND variant_id IS NOT NULL"
            ),
            sqlite_where=text(
                "archived_at IS NULL AND is_primary = 1 AND variant_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=True,
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    storage_backend: Mapped[str] = mapped_column(
        String(32), nullable=False, default="filesystem"
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

    product: Mapped[Product] = relationship(back_populates="images")
    variant: Mapped[ProductVariant | None] = relationship(back_populates="images")

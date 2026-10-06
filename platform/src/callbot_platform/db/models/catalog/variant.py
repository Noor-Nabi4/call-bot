"""Product variants and variant↔attribute links."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.catalog.attribute import ProductAttributeValue
    from callbot_platform.db.models.catalog.image import ProductImage
    from callbot_platform.db.models.catalog.product import Product


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        Index("ix_product_variants_tenant_product", "tenant_id", "product_id"),
        Index("ix_product_variants_tenant_sku", "tenant_id", "sku_normalized"),
        Index(
            "uq_product_variants_fingerprint",
            "tenant_id",
            "product_id",
            "attribute_fingerprint",
            unique=True,
            postgresql_where=text("archived_at IS NULL"),
            sqlite_where=text("archived_at IS NULL"),
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_product_variants_status",
        ),
        CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_product_variants_price_nonneg",
        ),
        CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_product_variants_cost_nonneg",
        ),
        CheckConstraint(
            "stock_on_hand IS NULL OR stock_on_hand >= 0",
            name="ck_product_variants_stock_nonneg",
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
    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    # Transitional quantity until Inventory domain owns stock.
    stock_on_hand: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    attribute_fingerprint: Mapped[str] = mapped_column(
        String(512), nullable=False, default=""
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

    product: Mapped[Product] = relationship(back_populates="variants")
    attribute_links: Mapped[list[ProductVariantAttributeValue]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )
    images: Mapped[list[ProductImage]] = relationship(back_populates="variant")


class ProductVariantAttributeValue(Base):
    __tablename__ = "product_variant_attribute_values"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "variant_id",
            "attribute_value_id",
            name="uq_variant_attr_value",
        ),
        Index(
            "ix_variant_attr_values_tenant_variant",
            "tenant_id",
            "variant_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    variant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
    )
    attribute_value_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_attribute_values.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    variant: Mapped[ProductVariant] = relationship(back_populates="attribute_links")
    attribute_value: Mapped[ProductAttributeValue] = relationship()

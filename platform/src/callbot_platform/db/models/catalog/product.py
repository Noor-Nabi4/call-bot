"""Core Product model."""

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
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.catalog.attribute import ProductAttribute
    from callbot_platform.db.models.catalog.brand import ProductBrand
    from callbot_platform.db.models.catalog.category import ProductCategory
    from callbot_platform.db.models.catalog.image import ProductImage
    from callbot_platform.db.models.catalog.variant import ProductVariant


class Product(Base):
    """First-class sellable catalog product (not a Dynamic CRM custom object)."""

    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_tenant_id", "tenant_id"),
        Index("ix_products_tenant_status", "tenant_id", "status"),
        Index("ix_products_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_products_tenant_category", "tenant_id", "category_id"),
        Index("ix_products_tenant_brand", "tenant_id", "brand_id"),
        Index("ix_products_tenant_name", "tenant_id", "name"),
        Index("ix_products_tenant_sku_normalized", "tenant_id", "sku_normalized"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_products_status",
        ),
        CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_products_price_nonneg",
        ),
        CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_products_cost_nonneg",
        ),
        CheckConstraint(
            "tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 100)",
            name="ck_products_tax_rate",
        ),
        CheckConstraint(
            "weight IS NULL OR weight >= 0",
            name="ck_products_weight_nonneg",
        ),
        CheckConstraint(
            "weight_unit IS NULL OR weight_unit IN ('KG', 'G', 'LB', 'OZ')",
            name="ck_products_weight_unit",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sku_normalized: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Money in tenant currency (tenants.currency). Scale 4 for tax-inclusive math.
    price: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    # Tax rate as percent 0-100 (not a full tax engine).
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(16, 4), nullable=True)
    weight_unit: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    category: Mapped[ProductCategory | None] = relationship(back_populates="products")
    brand: Mapped[ProductBrand | None] = relationship(back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    attributes: Mapped[list[ProductAttribute]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list[ProductImage]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

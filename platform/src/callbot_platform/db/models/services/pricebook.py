"""Pricebook, items, components, and tenant overrides (Phase 7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.catalog.variant import ProductVariant
    from callbot_platform.db.models.services.service import Service


class Pricebook(Base):
    __tablename__ = "pricebooks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_pricebooks_tenant_name"),
        Index("ix_pricebooks_tenant_id", "tenant_id"),
        Index("ix_pricebooks_tenant_status", "tenant_id", "status"),
        Index("ix_pricebooks_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_pricebooks_tenant_default", "tenant_id", "is_default"),
        Index("ix_pricebooks_tenant_effective", "tenant_id", "effective_from"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_pricebooks_status",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_pricebooks_effective_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    items: Mapped[list[PricebookItem]] = relationship(
        back_populates="pricebook", cascade="all, delete-orphan"
    )
    overrides: Mapped[list[PricebookOverride]] = relationship(
        back_populates="pricebook", cascade="all, delete-orphan"
    )


class PricebookItem(Base):
    __tablename__ = "pricebook_items"
    __table_args__ = (
        Index("ix_pricebook_items_tenant_id", "tenant_id"),
        Index("ix_pricebook_items_tenant_pricebook", "tenant_id", "pricebook_id"),
        Index("ix_pricebook_items_tenant_service", "tenant_id", "service_id"),
        Index(
            "ix_pricebook_items_tenant_effective",
            "tenant_id",
            "effective_from",
            "effective_until",
        ),
        Index("ix_pricebook_items_tenant_status", "tenant_id", "status"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_pricebook_items_status",
        ),
        CheckConstraint(
            "pricing_type IN ('FIXED', 'STARTING_AT', 'HOURLY', 'CUSTOM_QUOTE')",
            name="ck_pricebook_items_pricing_type",
        ),
        CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_pricebook_items_price_nonneg",
        ),
        CheckConstraint(
            "starting_price IS NULL OR starting_price >= 0",
            name="ck_pricebook_items_starting_nonneg",
        ),
        CheckConstraint(
            "hourly_rate IS NULL OR hourly_rate >= 0",
            name="ck_pricebook_items_hourly_nonneg",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_pricebook_items_effective_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pricebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricebooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    pricing_type: Mapped[str] = mapped_column(String(32), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    starting_price: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    hourly_rate: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    pricebook: Mapped[Pricebook] = relationship(back_populates="items")
    service: Mapped[Service] = relationship()
    components: Mapped[list[PricebookItemComponent]] = relationship(
        back_populates="pricebook_item", cascade="all, delete-orphan"
    )


class PricebookItemComponent(Base):
    __tablename__ = "pricebook_item_components"
    __table_args__ = (
        Index("ix_pb_item_components_tenant_id", "tenant_id"),
        Index(
            "ix_pb_item_components_tenant_item",
            "tenant_id",
            "pricebook_item_id",
        ),
        Index(
            "ix_pb_item_components_tenant_variant",
            "tenant_id",
            "product_variant_id",
        ),
        CheckConstraint(
            "component_type IN ('LABOR', 'MATERIAL')",
            name="ck_pb_item_components_type",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_pb_item_components_quantity_positive",
        ),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_pb_item_components_unit_price_nonneg",
        ),
        CheckConstraint(
            "(component_type = 'MATERIAL' AND product_variant_id IS NOT NULL) "
            "OR (component_type = 'LABOR')",
            name="ck_pb_item_components_material_variant",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pricebook_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricebook_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # LABOR: optional label; MATERIAL: must reference ProductVariant.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), nullable=False, default=Decimal("1")
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
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

    pricebook_item: Mapped[PricebookItem] = relationship(back_populates="components")
    product_variant: Mapped[ProductVariant | None] = relationship()


class PricebookOverride(Base):
    """Tenant/organization price override (tenant == organization on this platform).

    Precedence: override → pricebook item → service base_price.
    """

    __tablename__ = "pricebook_overrides"
    __table_args__ = (
        Index("ix_pricebook_overrides_tenant_id", "tenant_id"),
        Index(
            "ix_pricebook_overrides_tenant_lookup",
            "tenant_id",
            "pricebook_id",
            "service_id",
        ),
        Index(
            "ix_pricebook_overrides_tenant_effective",
            "tenant_id",
            "effective_from",
            "effective_until",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_pricebook_overrides_status",
        ),
        CheckConstraint(
            "pricing_type IS NULL OR pricing_type IN "
            "('FIXED', 'STARTING_AT', 'HOURLY', 'CUSTOM_QUOTE')",
            name="ck_pricebook_overrides_pricing_type",
        ),
        CheckConstraint(
            "override_price IS NULL OR override_price >= 0",
            name="ck_pricebook_overrides_price_nonneg",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_pricebook_overrides_effective_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    pricebook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricebooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
    )
    override_price: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    pricing_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    effective_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    pricebook: Mapped[Pricebook] = relationship(back_populates="overrides")
    service: Mapped[Service] = relationship()

"""Estimate ORM models (Phase 13 commercial quotes)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.crm import Customer, CustomerLocation


class Estimate(Base):
    """First-class commercial Estimate (not a Dynamic CRM custom object)."""

    __tablename__ = "estimates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "estimate_number", name="uq_estimates_tenant_estimate_number"
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_estimates_tenant_idempotency",
        ),
        Index("ix_estimates_tenant_id", "tenant_id"),
        Index("ix_estimates_tenant_status", "tenant_id", "status"),
        Index("ix_estimates_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_estimates_tenant_created", "tenant_id", "created_at"),
        Index("ix_estimates_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_estimates_tenant_valid_until", "tenant_id", "valid_until"),
        Index("ix_estimates_tenant_number", "tenant_id", "estimate_number"),
        CheckConstraint(
            "status IN ('DRAFT','SENT','VIEWED','APPROVED','REJECTED',"
            "'EXPIRED','CANCELLED','CONVERTED')",
            name="ck_estimates_status",
        ),
        CheckConstraint("subtotal >= 0", name="ck_estimates_subtotal_nonneg"),
        CheckConstraint("discount_total >= 0", name="ck_estimates_discount_nonneg"),
        CheckConstraint("tax_total >= 0", name="ck_estimates_tax_nonneg"),
        CheckConstraint("total >= 0", name="ck_estimates_total_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    estimate_number: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Estimate")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    total: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    estimate_discount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricebook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricebooks.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    customer: Mapped[Customer] = relationship(
        "Customer", foreign_keys="Estimate.customer_id"
    )
    location: Mapped[CustomerLocation | None] = relationship(
        "CustomerLocation", foreign_keys="Estimate.location_id"
    )
    items: Mapped[list[EstimateItem]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan"
    )
    status_history: Mapped[list[EstimateStatusHistory]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan"
    )
    conversions: Mapped[list[EstimateConversion]] = relationship(
        back_populates="estimate", cascade="all, delete-orphan"
    )


class EstimateItem(Base):
    __tablename__ = "estimate_items"
    __table_args__ = (
        Index("ix_estimate_items_tenant_estimate", "tenant_id", "estimate_id"),
        Index("ix_estimate_items_tenant_product", "tenant_id", "product_id"),
        Index("ix_estimate_items_tenant_service", "tenant_id", "service_id"),
        CheckConstraint(
            "item_type IN ('SERVICE','PRODUCT','CUSTOM')",
            name="ck_estimate_items_type",
        ),
        CheckConstraint("quantity > 0", name="ck_estimate_items_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_estimate_items_unit_price_nonneg"),
        CheckConstraint(
            "discount_total >= 0", name="ck_estimate_items_discount_nonneg"
        ),
        CheckConstraint("tax_total >= 0", name="ck_estimate_items_tax_nonneg"),
        CheckConstraint("line_subtotal >= 0", name="ck_estimate_items_subtotal_nonneg"),
        CheckConstraint("line_total >= 0", name="ck_estimate_items_total_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    pricebook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pricebooks.id", ondelete="SET NULL"),
        nullable=True,
    )
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    description_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_snapshot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pricing_source_snapshot: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    tax_rate_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 4), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("1")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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

    estimate: Mapped[Estimate] = relationship(back_populates="items")


class EstimateStatusHistory(Base):
    """Append-only estimate status history."""

    __tablename__ = "estimate_status_history"
    __table_args__ = (
        Index("ix_estimate_status_history_tenant_estimate", "tenant_id", "estimate_id"),
        Index("ix_estimate_status_history_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    estimate: Mapped[Estimate] = relationship(back_populates="status_history")


class EstimateConversion(Base):
    """Idempotent Estimate → Job/Order conversion record."""

    __tablename__ = "estimate_conversions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "estimate_id",
            name="uq_estimate_conversions_tenant_estimate",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_estimate_conversions_tenant_idempotency",
        ),
        Index(
            "ix_estimate_conversions_tenant_target",
            "tenant_id",
            "target_type",
            "target_id",
        ),
        CheckConstraint(
            "target_type IN ('JOB','ORDER')",
            name="ck_estimate_conversions_target_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    estimate: Mapped[Estimate] = relationship(back_populates="conversions")


class EstimateNumberCounter(Base):
    """Per-tenant monotonic estimate number sequence (concurrency-safe)."""

    __tablename__ = "estimate_number_counters"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_estimate_number_counters_tenant"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

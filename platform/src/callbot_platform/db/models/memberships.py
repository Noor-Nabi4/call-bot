"""Customer memberships (Phase 20) — plans, subscriptions, entitlements."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

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

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class MembershipPlan(Base):
    __tablename__ = "membership_plans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_membership_plans_tenant_name"),
        Index("ix_membership_plans_tenant_status", "tenant_id", "status"),
        Index("ix_membership_plans_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','INACTIVE','ARCHIVED')",
            name="ck_membership_plans_status",
        ),
        CheckConstraint(
            "monthly_price >= 0", name="ck_membership_plans_monthly_nonneg"
        ),
        CheckConstraint("annual_price >= 0", name="ck_membership_plans_annual_nonneg"),
        CheckConstraint(
            "(discount_type IS NULL AND discount_value IS NULL) OR "
            "(discount_type IN ('PERCENTAGE','FIXED_AMOUNT') AND "
            "discount_value IS NOT NULL)",
            name="ck_membership_plans_discount_shape",
        ),
        CheckConstraint(
            "discount_value IS NULL OR discount_value >= 0",
            name="ck_membership_plans_discount_nonneg",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    monthly_price: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    annual_price: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    priority_scheduling: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    discount_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discount_value: Mapped[Decimal | None] = mapped_column(
        Numeric(19, 4), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    included_services: Mapped[list[MembershipPlanService]] = relationship(
        "MembershipPlanService",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class MembershipPlanService(Base):
    __tablename__ = "membership_plan_services"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "plan_id",
            "service_id",
            name="uq_membership_plan_services_plan_service",
        ),
        Index("ix_membership_plan_services_tenant_plan", "tenant_id", "plan_id"),
        CheckConstraint(
            "included_quantity > 0",
            name="ck_membership_plan_services_qty_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    included_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    plan: Mapped[MembershipPlan] = relationship(
        "MembershipPlan", back_populates="included_services"
    )


class CustomerMembership(Base):
    __tablename__ = "customer_memberships"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_customer_memberships_tenant_idempotency",
        ),
        Index("ix_customer_memberships_tenant_status", "tenant_id", "status"),
        Index("ix_customer_memberships_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_customer_memberships_tenant_plan", "tenant_id", "plan_id"),
        Index(
            "ix_customer_memberships_tenant_period_end",
            "tenant_id",
            "current_period_end",
        ),
        Index("ix_customer_memberships_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(
            "status IN ('PENDING','ACTIVE','PAST_DUE','CANCELLED','EXPIRED','PAUSED')",
            name="ck_customer_memberships_status",
        ),
        CheckConstraint(
            "billing_interval IN ('MONTHLY','ANNUAL')",
            name="ck_customer_memberships_interval",
        ),
        CheckConstraint(
            "pending_billing_interval IS NULL OR "
            "pending_billing_interval IN ('MONTHLY','ANNUAL')",
            name="ck_customer_memberships_pending_interval",
        ),
        CheckConstraint(
            "current_period_end > current_period_start",
            name="ck_customer_memberships_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    renewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pending_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    pending_billing_interval: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    last_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
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


class MembershipHistory(Base):
    __tablename__ = "membership_history"
    __table_args__ = (
        Index(
            "ix_membership_history_tenant_membership",
            "tenant_id",
            "membership_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("membership_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


class MembershipBillingPeriod(Base):
    __tablename__ = "membership_billing_periods"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "membership_id",
            "period_start",
            name="uq_membership_billing_period_start",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_membership_billing_periods_idempotency",
        ),
        Index(
            "ix_membership_billing_periods_tenant_invoice",
            "tenant_id",
            "invoice_id",
        ),
        Index(
            "ix_membership_billing_periods_tenant_membership",
            "tenant_id",
            "membership_id",
        ),
        CheckConstraint(
            "status IN ('PENDING','PAID','VOID','FAILED')",
            name="ck_membership_billing_periods_status",
        ),
        CheckConstraint(
            "amount >= 0", name="ck_membership_billing_periods_amount_nonneg"
        ),
        CheckConstraint(
            "period_end > period_start",
            name="ck_membership_billing_periods_window",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
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


class MembershipEntitlementUsage(Base):
    __tablename__ = "membership_entitlement_usage"
    __table_args__ = (
        UniqueConstraint(
            "membership_id",
            "appointment_id",
            "service_id",
            name="uq_membership_entitlement_usage_appt",
        ),
        Index(
            "ix_membership_entitlement_usage_tenant_membership",
            "tenant_id",
            "membership_id",
        ),
        Index(
            "ix_membership_entitlement_usage_tenant_appointment",
            "tenant_id",
            "appointment_id",
        ),
        CheckConstraint("quantity > 0", name="ck_membership_entitlement_usage_qty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=False,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

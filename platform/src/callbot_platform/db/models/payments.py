"""Customer invoice payments (Phase 19) — Stripe Checkout, not SaaS billing."""

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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_payments_tenant_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider_checkout_session_id",
            name="uq_payments_tenant_checkout_session",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider_payment_intent_id",
            name="uq_payments_tenant_payment_intent",
        ),
        Index("ix_payments_tenant_status", "tenant_id", "status"),
        Index("ix_payments_tenant_invoice", "tenant_id", "invoice_id"),
        Index("ix_payments_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_payments_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(
            "status IN ("
            "'PENDING','PROCESSING','SUCCEEDED','FAILED',"
            "'CANCELLED','REFUNDED','PARTIALLY_REFUNDED'"
            ")",
            name="ck_payments_status",
        ),
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("refunded_amount >= 0", name="ck_payments_refunded_nonneg"),
        CheckConstraint(
            "provider IN ('stripe')",
            name="ck_payments_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="stripe")
    provider_checkout_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    provider_payment_intent_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    provider_charge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    payment_method_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    refunded_amount: Mapped[Decimal] = mapped_column(
        Numeric(19, 4), nullable=False, default=Decimal("0")
    )
    applied_to_invoice: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_request_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


class PaymentRefund(Base):
    """Local refund ledger for Stripe refunds against a payment."""

    __tablename__ = "payment_refunds"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_payment_refunds_tenant_idempotency",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider_refund_id",
            name="uq_payment_refunds_tenant_provider_refund",
        ),
        Index("ix_payment_refunds_tenant_payment", "tenant_id", "payment_id"),
        CheckConstraint("amount > 0", name="ck_payment_refunds_amount_positive"),
        CheckConstraint(
            "status IN ('PENDING','SUCCEEDED','FAILED')",
            name="ck_payment_refunds_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(19, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    provider_refund_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
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

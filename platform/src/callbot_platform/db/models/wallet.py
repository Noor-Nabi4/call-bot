"""Internal USD wallet models (platform closed-loop credits)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
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
    from callbot_platform.db.models.tenant import Tenant


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_wallets_tenant"),
        Index("ix_wallets_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    available_balance_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    reserved_balance_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
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

    tenant: Mapped[Tenant] = relationship()
    transactions: Mapped[list[WalletTransaction]] = relationship(
        back_populates="wallet"
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_wallet_transactions_tenant_idempotency",
        ),
        Index("ix_wallet_transactions_wallet_created", "wallet_id", "created_at"),
        Index("ix_wallet_transactions_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # CREDIT | DEBIT | REFUND | ADJUSTMENT
    transaction_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    balance_after_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # TOPUP | SUBSCRIPTION | USAGE | ADMIN | REFUND | RESERVATION
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    wallet: Mapped[Wallet] = relationship(back_populates="transactions")


class WalletTopup(Base):
    __tablename__ = "wallet_topups"
    __table_args__ = (
        UniqueConstraint(
            "stripe_checkout_session_id", name="uq_wallet_topups_checkout_session"
        ),
        UniqueConstraint(
            "stripe_payment_intent_id", name="uq_wallet_topups_payment_intent"
        ),
        Index("ix_wallet_topups_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    # PENDING | SUCCEEDED | FAILED | CANCELED | REFUNDED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wallet_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    credited_at: Mapped[datetime | None] = mapped_column(
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


class WalletReservation(Base):
    __tablename__ = "wallet_reservations"
    __table_args__ = (
        Index("ix_wallet_reservations_wallet_status", "wallet_id", "status"),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_wallet_reservations_tenant_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # OPEN | CAPTURED | RELEASED | EXPIRED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(
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


class WalletSettings(Base):
    __tablename__ = "wallet_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_wallet_settings_tenant"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    low_balance_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    critical_balance_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=500
    )
    auto_topup_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    auto_topup_threshold_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1000
    )
    auto_topup_amount_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5000
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


class UsageCharge(Base):
    """Per-call voice overage charged against the wallet."""

    __tablename__ = "usage_charges"
    __table_args__ = (
        UniqueConstraint("tenant_id", "call_id", name="uq_usage_charges_tenant_call"),
        Index("ix_usage_charges_tenant_period", "tenant_id", "billing_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    billing_period: Mapped[str] = mapped_column(String(16), nullable=False)  # YYYY-MM
    billable_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    billable_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    included_minutes_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overage_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_per_minute_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # PENDING | CHARGED | FAILED | SKIPPED
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    wallet_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallet_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

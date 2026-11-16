"""Phase 32 usage ledger — financial-adjacent usage events (tenant-scoped)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class UsageLedgerEntry(Base):
    __tablename__ = "usage_ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_usage_ledger_entries_tenant_idempotency",
        ),
        Index(
            "ix_usage_ledger_tenant_type_occurred",
            "tenant_id",
            "usage_type",
            "occurred_at",
        ),
        Index("ix_usage_ledger_tenant_period", "tenant_id", "billing_period"),
        Index(
            "ix_usage_ledger_tenant_source",
            "tenant_id",
            "source_type",
            "source_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    usage_type: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False)
    pricing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    cost_basis: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    usage_provenance: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTUAL_INTERNAL"
    )
    billing_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="usage")
    meta_json: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


class UsageAlertDelivery(Base):
    __tablename__ = "usage_alert_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "alert_key",
            "threshold_pct",
            "billing_period",
            name="uq_usage_alert_deliveries_dedupe",
        ),
        Index(
            "ix_usage_alert_deliveries_tenant_period",
            "tenant_id",
            "billing_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    alert_key: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="outbox")
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    meta_json: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )

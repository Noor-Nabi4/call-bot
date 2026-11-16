"""First-class Service catalog model (Phase 7)."""

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
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.services.category import ServiceCategory


class Service(Base):
    """Tenant-scoped service offering (not a Dynamic CRM custom object)."""

    __tablename__ = "services"
    __table_args__ = (
        Index("ix_services_tenant_id", "tenant_id"),
        Index("ix_services_tenant_status", "tenant_id", "status"),
        Index("ix_services_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_services_tenant_category", "tenant_id", "category_id"),
        Index("ix_services_tenant_name", "tenant_id", "name"),
        Index("ix_services_tenant_code_normalized", "tenant_id", "code_normalized"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_services_status",
        ),
        CheckConstraint(
            "pricing_type IN ('FIXED', 'STARTING_AT', 'HOURLY', 'CUSTOM_QUOTE')",
            name="ck_services_pricing_type",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_services_duration_positive",
        ),
        CheckConstraint(
            "base_price IS NULL OR base_price >= 0",
            name="ck_services_base_price_nonneg",
        ),
        CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_services_cost_nonneg",
        ),
        CheckConstraint(
            "tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 100)",
            name="ck_services_tax_rate",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    code_normalized: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Catalog base price (fallback when no pricebook item applies).
    base_price: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(19, 4), nullable=True)
    # Tax rate as percent 0-100 (not a full tax engine).
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    pricing_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="FIXED"
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

    category: Mapped[ServiceCategory | None] = relationship(back_populates="services")

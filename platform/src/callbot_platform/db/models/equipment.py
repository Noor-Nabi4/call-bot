"""Equipment / assets ORM (Phase 21)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        Index("ix_equipment_tenant_status", "tenant_id", "status"),
        Index("ix_equipment_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_equipment_tenant_location", "tenant_id", "location_id"),
        Index("ix_equipment_tenant_manufacturer", "tenant_id", "manufacturer"),
        Index("ix_equipment_tenant_model", "tenant_id", "model"),
        Index("ix_equipment_tenant_install", "tenant_id", "installation_date"),
        Index("ix_equipment_tenant_warranty_end", "tenant_id", "warranty_end_date"),
        Index("ix_equipment_tenant_created", "tenant_id", "created_at"),
        # Partial unique — mirrors 0049_equipment; authoritative under concurrent creates.
        Index(
            "uq_equipment_tenant_serial_norm",
            "tenant_id",
            "serial_number_normalized",
            unique=True,
            postgresql_where=text("serial_number_normalized IS NOT NULL"),
            sqlite_where=text("serial_number_normalized IS NOT NULL"),
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','RETIRED','REMOVED')",
            name="ck_equipment_status",
        ),
        CheckConstraint(
            "warranty_end_date IS NULL OR warranty_start_date IS NULL OR "
            "warranty_end_date >= warranty_start_date",
            name="ck_equipment_warranty_dates",
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
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    manufacturer: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    serial_number_normalized: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    installation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warranty_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
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

    attachments: Mapped[list[EquipmentAttachment]] = relationship(
        "EquipmentAttachment",
        back_populates="equipment",
        cascade="all, delete-orphan",
    )


class EquipmentAttachment(Base):
    __tablename__ = "equipment_attachments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "object_key",
            name="uq_equipment_attachments_tenant_object_key",
        ),
        Index(
            "ix_equipment_attachments_tenant_equipment",
            "tenant_id",
            "equipment_id",
        ),
        CheckConstraint(
            "kind IN ('PHOTO','INSTALLATION','REPAIR','BEFORE','AFTER','OTHER')",
            name="ck_equipment_attachments_kind",
        ),
        CheckConstraint(
            "size_bytes >= 0", name="ck_equipment_attachments_size_nonneg"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="PHOTO")
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

    equipment: Mapped[Equipment] = relationship(back_populates="attachments")

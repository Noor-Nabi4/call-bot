"""Product option attributes and values (e.g. Color / Size)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.catalog.product import Product


class ProductAttribute(Base):
    __tablename__ = "product_attributes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "product_id",
            "name_normalized",
            name="uq_product_attributes_name",
        ),
        Index("ix_product_attributes_tenant_product", "tenant_id", "product_id"),
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
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    product: Mapped[Product] = relationship(back_populates="attributes")
    values: Mapped[list[ProductAttributeValue]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan"
    )


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "attribute_id",
            "value_normalized",
            name="uq_product_attribute_values",
        ),
        Index(
            "ix_product_attribute_values_tenant_attr",
            "tenant_id",
            "attribute_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product_attributes.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    value_normalized: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    attribute: Mapped[ProductAttribute] = relationship(back_populates="values")

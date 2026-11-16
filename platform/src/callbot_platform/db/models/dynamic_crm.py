"""Custom objects, field values, and CRM relationship models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid


class OrganizationCustomObjectDefinition(Base):
    __tablename__ = "organization_custom_object_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "object_key",
            name="uq_org_custom_object_definitions_tenant_key",
        ),
        Index("ix_org_custom_object_definitions_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    object_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    plural_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon: Mapped[str] = mapped_column(String(64), nullable=False, default="box")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ORG_CUSTOM"
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
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrganizationCustomObjectRecord(Base):
    __tablename__ = "organization_custom_object_records"
    __table_args__ = (
        Index(
            "ix_org_custom_object_records_tenant_object",
            "tenant_id",
            "object_definition_id",
        ),
        Index("ix_org_custom_object_records_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    object_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_custom_object_definitions.id", ondelete="CASCADE"),
        nullable=False,
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
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CrmCustomFieldValue(Base):
    """Typed EAV values for module records or custom-object records."""

    __tablename__ = "crm_custom_field_values"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "field_definition_id",
            "record_id",
            name="uq_crm_custom_field_values_tenant_field_record",
        ),
        Index("ix_crm_custom_field_values_tenant_id", "tenant_id"),
        Index(
            "ix_crm_custom_field_values_tenant_record",
            "tenant_id",
            "record_type",
            "record_id",
        ),
        Index(
            "ix_crm_custom_field_values_tenant_field_text",
            "tenant_id",
            "field_definition_id",
            "value_text",
        ),
        Index(
            "ix_crm_custom_field_values_tenant_field_number",
            "tenant_id",
            "field_definition_id",
            "value_number",
        ),
        Index(
            "ix_crm_custom_field_values_tenant_field_date",
            "tenant_id",
            "field_definition_id",
            "value_date",
        ),
        Index(
            "ix_crm_custom_field_values_tenant_field_datetime",
            "tenant_id",
            "field_definition_id",
            "value_datetime",
        ),
        Index(
            "ix_crm_custom_field_values_tenant_field_boolean",
            "tenant_id",
            "field_definition_id",
            "value_boolean",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    field_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_crm_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    # module | object
    record_type: Mapped[str] = mapped_column(String(16), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    value_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    value_json: Mapped[Any | None] = mapped_column(JsonType, nullable=True)
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


class OrganizationCrmRelationshipDefinition(Base):
    __tablename__ = "organization_crm_relationship_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "relationship_key",
            name="uq_org_crm_relationship_definitions_tenant_key",
        ),
        Index("ix_org_crm_relationship_definitions_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # module | object
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_key: Mapped[str] = mapped_column(String(64), nullable=False)
    relationship_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    inverse_label: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cardinality: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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


class OrganizationCrmRelationshipLink(Base):
    """Relationship instances (including many-to-many junction rows)."""

    __tablename__ = "organization_crm_relationship_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "definition_id",
            "source_record_id",
            "target_record_id",
            name="uq_org_crm_relationship_links_edge",
        ),
        Index("ix_org_crm_relationship_links_tenant_id", "tenant_id"),
        Index(
            "ix_org_crm_relationship_links_tenant_def_source",
            "tenant_id",
            "definition_id",
            "source_record_id",
        ),
        Index(
            "ix_org_crm_relationship_links_tenant_def_target",
            "tenant_id",
            "definition_id",
            "target_record_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_crm_relationship_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    target_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

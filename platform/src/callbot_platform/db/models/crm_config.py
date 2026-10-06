"""Tenant-owned CRM configuration metadata (modules/statuses/fields/workflows)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
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


class OrganizationCrmConfiguration(Base):
    __tablename__ = "organization_crm_configurations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", name="uq_organization_crm_configurations_tenant_id"
        ),
        Index("ix_organization_crm_configurations_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    industry_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    business_model_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    setup_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    settings_json: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    applied_at: Mapped[datetime | None] = mapped_column(
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


class OrganizationCrmModule(Base):
    __tablename__ = "organization_crm_modules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "module_key",
            name="uq_organization_crm_modules_tenant_module",
        ),
        Index("ix_organization_crm_modules_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="template")
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


class OrganizationCrmStatus(Base):
    __tablename__ = "organization_crm_statuses"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "module_key",
            "status_key",
            name="uq_organization_crm_statuses_tenant_module_status",
        ),
        Index("ix_organization_crm_statuses_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    module_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status_key: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="template")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


class OrganizationCrmField(Base):
    __tablename__ = "organization_crm_fields"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "owner_scope",
            "owner_key",
            "field_key",
            name="uq_organization_crm_fields_tenant_owner_field",
        ),
        Index("ix_organization_crm_fields_tenant_id", "tenant_id"),
        Index(
            "ix_organization_crm_fields_tenant_owner",
            "tenant_id",
            "owner_scope",
            "owner_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # Legacy module-only key kept for Phase 2 template compatibility.
    module_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # module | object
    owner_scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="module"
    )
    # Module key or custom object_key
    owner_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    field_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TEXT")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    default_value: Mapped[Any | None] = mapped_column(JsonType, nullable=True)
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    validation_rules: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="template")
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


class OrganizationCrmWorkflow(Base):
    __tablename__ = "organization_crm_workflows"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workflow_key",
            name="uq_organization_crm_workflows_tenant_workflow",
        ),
        Index("ix_organization_crm_workflows_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    workflow_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    module_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stages_json: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="template")
    definition_json: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

"""Phase 25 communication template ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
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


class CommunicationTemplate(Base):
    __tablename__ = "communication_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "channel",
            "template_key",
            name="uq_communication_templates_tenant_channel_key",
        ),
        Index(
            "ix_communication_templates_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_communication_templates_tenant_channel_key",
            "tenant_id",
            "channel",
            "template_key",
        ),
        CheckConstraint(
            "channel IN ('SMS','EMAIL')",
            name="ck_communication_templates_channel",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','ARCHIVED')",
            name="ck_communication_templates_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    active_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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

    versions: Mapped[list[CommunicationTemplateVersion]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="CommunicationTemplateVersion.version",
    )


class CommunicationTemplateVersion(Base):
    __tablename__ = "communication_template_versions"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "version",
            name="uq_communication_template_versions_template_version",
        ),
        Index(
            "ix_comm_template_versions_tenant_template",
            "tenant_id",
            "template_id",
        ),
        Index(
            "ix_comm_template_versions_template_status",
            "template_id",
            "status",
        ),
        CheckConstraint(
            "status IN ('DRAFT','ACTIVE','SUPERSEDED')",
            name="ck_communication_template_versions_status",
        ),
        CheckConstraint("version >= 1", name="ck_communication_template_versions_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communication_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    template: Mapped[CommunicationTemplate] = relationship(back_populates="versions")

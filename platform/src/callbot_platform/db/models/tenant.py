"""Tenant and telephony-related ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.crm import Customer, TenantAgentSettings
    from callbot_platform.db.models.handoff import (
        TenantHandoffSettings,
        TenantRetentionSettings,
    )
    from callbot_platform.db.models.jobs import Job, Technician, TenantUser
    from callbot_platform.db.models.knowledge import KnowledgeArticle
    from callbot_platform.db.models.scheduling import (
        Appointment,
        TenantScheduleSettings,
    )


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    phone_numbers: Mapped[list[TenantPhoneNumber]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    twilio_subaccount: Mapped[TenantTwilioSubaccount | None] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    agent_settings: Mapped[TenantAgentSettings | None] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    customers: Mapped[list[Customer]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    schedule_settings: Mapped[TenantScheduleSettings | None] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    users: Mapped[list[TenantUser]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    technicians: Mapped[list[Technician]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    knowledge_articles: Mapped[list[KnowledgeArticle]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    handoff_settings: Mapped[TenantHandoffSettings | None] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )
    retention_settings: Mapped[TenantRetentionSettings | None] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )


class TenantPhoneNumber(Base):
    __tablename__ = "tenant_phone_numbers"
    __table_args__ = (
        UniqueConstraint("e164", name="uq_tenant_phone_numbers_e164"),
        Index("ix_tenant_phone_numbers_tenant_id", "tenant_id"),
        Index("ix_tenant_phone_numbers_livekit_trunk", "livekit_inbound_trunk_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="twilio")
    e164: Mapped[str] = mapped_column(String(32), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    twilio_account_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    twilio_trunk_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    livekit_inbound_trunk_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    livekit_dispatch_rule_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    connection_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_setup"
    )
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified"
    )
    onboarding_path: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual"
    )
    oauth_connection_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verification_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    provisioning_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none"
    )
    provisioning_details: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    last_purchase_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    tenant: Mapped[Tenant] = relationship(back_populates="phone_numbers")


class TenantTwilioSubaccount(Base):
    __tablename__ = "tenant_twilio_subaccounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_twilio_subaccounts_tenant"),
        UniqueConstraint(
            "twilio_subaccount_sid", name="uq_tenant_twilio_subaccounts_sid"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    twilio_subaccount_sid: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_auth_token: Mapped[str] = mapped_column(Text, nullable=False)
    friendly_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="twilio_subaccount")


class TelephonyAuditEvent(Base):
    __tablename__ = "telephony_audit_events"
    __table_args__ = (Index("ix_telephony_audit_tenant_id", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_ids: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_summary: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )


class TelephonyIdempotencyKey(Base):
    __tablename__ = "telephony_idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "operation", "key", name="uq_telephony_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    response_json: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

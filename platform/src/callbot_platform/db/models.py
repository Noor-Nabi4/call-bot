"""SQLAlchemy models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Use JSON for SQLite test compatibility; Postgres still stores JSON.
JsonType = JSON().with_variant(JSONB(), "postgresql")


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
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
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
    auth_method: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
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
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
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
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
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
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )


class TenantAgentSettings(Base):
    __tablename__ = "tenant_agent_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_agent_settings_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    business_prompt_facts: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    voice: Mapped[str] = mapped_column(String(64), nullable=False, default="marin")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="agent_settings")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customers_tenant_id", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="customers")
    phones: Mapped[list[CustomerPhone]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    leads: Mapped[list[Lead]] = relationship(back_populates="customer")
    calls: Mapped[list[Call]] = relationship(back_populates="customer")
    appointments: Mapped[list[Appointment]] = relationship(
        back_populates="customer"
    )


class CustomerPhone(Base):
    __tablename__ = "customer_phones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "e164", name="uq_customer_phones_tenant_e164"),
        Index("ix_customer_phones_tenant_id", "tenant_id"),
        Index("ix_customer_phones_customer_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    e164: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    customer: Mapped[Customer] = relationship(back_populates="phones")


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_tenant_id", "tenant_id"),
        Index("ix_calls_customer_id", "customer_id"),
        Index("ix_calls_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    disconnect_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict)
    caller_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    called_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telephony_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

    customer: Mapped[Customer | None] = relationship(back_populates="calls")
    leads: Mapped[list[Lead]] = relationship(back_populates="call")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_leads_tenant_idempotency"
        ),
        Index("ix_leads_tenant_id", "tenant_id"),
        Index("ix_leads_customer_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    service_type: Mapped[str] = mapped_column(String(128), nullable=False)
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_time_window: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_code: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    customer: Mapped[Customer] = relationship(back_populates="leads")
    call: Mapped[Call | None] = relationship(back_populates="leads")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="lead")


def default_weekly_hours() -> dict[str, list[list[str]]]:
    day = [["09:00", "17:00"]]
    return {
        "mon": list(day),
        "tue": list(day),
        "wed": list(day),
        "thu": list(day),
        "fri": list(day),
        "sat": [],
        "sun": [],
    }


class TenantScheduleSettings(Base):
    __tablename__ = "tenant_schedule_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_schedule_settings_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    slot_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    booking_horizon_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=14
    )
    weekly_hours: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=default_weekly_hours
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="schedule_settings")


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_appointments_tenant_idempotency"
        ),
        Index("ix_appointments_tenant_id", "tenant_id"),
        Index("ix_appointments_tenant_starts", "tenant_id", "starts_at"),
        Index("ix_appointments_customer_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    service_type: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_code: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    tenant: Mapped[Tenant] = relationship(back_populates="appointments")
    customer: Mapped[Customer] = relationship(back_populates="appointments")
    lead: Mapped[Lead | None] = relationship(back_populates="appointments")
    call: Mapped[Call | None] = relationship()
    notifications: Mapped[list[NotificationOutbox]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan"
    )


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        Index("ix_notification_outbox_tenant_id", "tenant_id"),
        Index("ix_notification_outbox_appointment_id", "appointment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    appointment: Mapped[Appointment] = relationship(back_populates="notifications")


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
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )

"""CRM-related ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid
from callbot_platform.db.models.tenant import Tenant

if TYPE_CHECKING:
    from callbot_platform.db.models.jobs import Job
    from callbot_platform.db.models.scheduling import Appointment


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
    assistant_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supported_languages: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    response_style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    service_areas: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    business_hours_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_disclosure_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    handoff_rules_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    restricted_topics: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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

    tenant: Mapped[Tenant] = relationship(back_populates="customers")
    phones: Mapped[list[CustomerPhone]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    leads: Mapped[list[Lead]] = relationship(back_populates="customer")
    calls: Mapped[list[Call]] = relationship(back_populates="customer")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="customer")
    jobs: Mapped[list[Job]] = relationship(back_populates="customer")


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
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
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
    billable_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    disconnect_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    caller_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    called_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telephony_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
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
    preferred_time_window: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_code: Mapped[str] = mapped_column(String(32), nullable=False)
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

    customer: Mapped[Customer] = relationship(back_populates="leads")
    call: Mapped[Call | None] = relationship(back_populates="leads")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="lead")

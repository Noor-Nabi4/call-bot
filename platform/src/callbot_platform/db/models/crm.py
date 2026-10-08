"""CRM-related ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid
from callbot_platform.db.models.tenant import Tenant

if TYPE_CHECKING:
    from callbot_platform.db.models.jobs import Job, TenantUser
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
    """First-class tenant CRM identity.

    ``name`` is the canonical display name (voice-era callers depend on it).
    ``first_name`` / ``last_name`` are optional structured parts; when present
    without an explicit display name they are used to derive ``name``.
    """

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_tenant_id", "tenant_id"),
        Index("ix_customers_tenant_email_normalized", "tenant_id", "email_normalized"),
        Index("ix_customers_tenant_status", "tenant_id", "status"),
        Index("ix_customers_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_customers_tenant_created", "tenant_id", "created_at"),
        Index("ix_customers_tenant_name", "tenant_id", "name"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_customers_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_normalized: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sms_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    marketing_sms_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    marketing_email_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    tenant: Mapped[Tenant] = relationship(back_populates="customers")
    phones: Mapped[list[CustomerPhone]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    locations: Mapped[list[CustomerLocation]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    tag_links: Mapped[list[CustomerTagLink]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    customer_notes: Mapped[list[CustomerNote]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    leads: Mapped[list[Lead]] = relationship(
        back_populates="customer", foreign_keys="Lead.customer_id"
    )
    calls: Mapped[list[Call]] = relationship(back_populates="customer")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="customer")
    jobs: Mapped[list[Job]] = relationship(back_populates="customer")


class CustomerPhone(Base):
    __tablename__ = "customer_phones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "e164", name="uq_customer_phones_tenant_e164"),
        Index("ix_customer_phones_tenant_id", "tenant_id"),
        Index("ix_customer_phones_customer_id", "customer_id"),
        Index("ix_customer_phones_tenant_e164", "tenant_id", "e164"),
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


class CustomerLocation(Base):
    __tablename__ = "customer_locations"
    __table_args__ = (
        Index("ix_customer_locations_tenant_id", "tenant_id"),
        Index("ix_customer_locations_tenant_customer", "tenant_id", "customer_id"),
        Index(
            "ix_customer_locations_tenant_postal",
            "tenant_id",
            "postal_code",
        ),
        Index("ix_customer_locations_tenant_city", "tenant_id", "city"),
        Index(
            "uq_customer_locations_one_primary",
            "tenant_id",
            "customer_id",
            unique=True,
            postgresql_where=text("archived_at IS NULL AND is_primary IS TRUE"),
            sqlite_where=text("archived_at IS NULL AND is_primary = 1"),
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_customer_locations_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_customer_locations_longitude",
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
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address_line_1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    access_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    customer: Mapped[Customer] = relationship(back_populates="locations")


class CustomerTag(Base):
    __tablename__ = "customer_tags"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name_normalized", name="uq_customer_tags_tenant_name"
        ),
        Index("ix_customer_tags_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    links: Mapped[list[CustomerTagLink]] = relationship(back_populates="tag")


class CustomerTagLink(Base):
    __tablename__ = "customer_tag_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "tag_id",
            name="uq_customer_tag_links_assignment",
        ),
        Index("ix_customer_tag_links_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_customer_tag_links_tenant_tag", "tenant_id", "tag_id"),
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
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customer_tags.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    customer: Mapped[Customer] = relationship(back_populates="tag_links")
    tag: Mapped[CustomerTag] = relationship(back_populates="links")


class CustomerNote(Base):
    """Historical customer notes (profile ``notes`` remains a short summary)."""

    __tablename__ = "customer_notes"
    __table_args__ = (
        Index("ix_customer_notes_tenant_id", "tenant_id"),
        Index("ix_customer_notes_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_customer_notes_tenant_created", "tenant_id", "created_at"),
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
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    customer: Mapped[Customer] = relationship(back_populates="customer_notes")
    author: Mapped[TenantUser | None] = relationship()


class Call(Base):
    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_tenant_id", "tenant_id"),
        Index("ix_calls_customer_id", "customer_id"),
        Index("ix_calls_job_id", "job_id"),
        Index("ix_calls_tenant_ended_at", "tenant_id", "ended_at"),
        Index("ix_calls_tenant_status_started", "tenant_id", "status", "started_at"),
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
    disposition_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    quality_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quality_reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    customer: Mapped[Customer | None] = relationship(back_populates="calls")
    leads: Mapped[list[Lead]] = relationship(back_populates="call")


class Lead(Base):
    """First-class Lead CRM row (Phase 8). Voice create path remains supported."""

    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_leads_tenant_idempotency"
        ),
        Index("ix_leads_tenant_id", "tenant_id"),
        Index("ix_leads_customer_id", "customer_id"),
        Index("ix_leads_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_leads_tenant_status", "tenant_id", "status"),
        Index("ix_leads_tenant_owner", "tenant_id", "owner_user_id"),
        Index("ix_leads_tenant_source", "tenant_id", "source"),
        Index("ix_leads_tenant_priority", "tenant_id", "priority"),
        Index("ix_leads_tenant_service", "tenant_id", "service_id"),
        Index("ix_leads_tenant_product", "tenant_id", "product_id"),
        Index("ix_leads_tenant_archived", "tenant_id", "archived_at"),
        Index("ix_leads_tenant_updated", "tenant_id", "updated_at"),
        Index("ix_leads_tenant_created", "tenant_id", "created_at"),
        CheckConstraint(
            "status IN ('NEW', 'QUALIFIED', 'CONTACTED', 'BOOKED', 'WON', 'LOST')",
            name="ck_leads_status",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="ck_leads_priority",
        ),
        CheckConstraint(
            "source IN ('PHONE', 'WEBSITE', 'REFERRAL', 'SOCIAL', 'EMAIL', "
            "'AD', 'WALK_IN', 'AI_AGENT', 'OTHER')",
            name="ck_leads_source",
        ),
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
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    # Legacy voice fields (kept for AI/voice compatibility).
    service_type: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    urgency: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_time_window: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_code: Mapped[str] = mapped_column(String(32), nullable=False)

    # Phase 8 CRM fields
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="OTHER")
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Non-authoritative prospect contact when customer_id is null.
    prospect_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prospect_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prospect_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    converted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    converted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    converted_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
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

    customer: Mapped[Customer | None] = relationship(
        back_populates="leads", foreign_keys=[customer_id]
    )
    call: Mapped[Call | None] = relationship(back_populates="leads")
    appointments: Mapped[list[Appointment]] = relationship(back_populates="lead")
    lead_notes: Mapped[list[LeadNote]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    activities: Mapped[list[LeadActivity]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )
    conversion: Mapped[LeadConversion | None] = relationship(
        back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )


class LeadNote(Base):
    __tablename__ = "lead_notes"
    __table_args__ = (
        Index("ix_lead_notes_tenant_id", "tenant_id"),
        Index("ix_lead_notes_tenant_lead", "tenant_id", "lead_id"),
        Index("ix_lead_notes_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
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

    lead: Mapped[Lead] = relationship(back_populates="lead_notes")


class LeadActivity(Base):
    __tablename__ = "lead_activities"
    __table_args__ = (
        Index("ix_lead_activities_tenant_id", "tenant_id"),
        Index("ix_lead_activities_tenant_lead", "tenant_id", "lead_id"),
        Index("ix_lead_activities_tenant_created", "tenant_id", "created_at"),
        Index("ix_lead_activities_tenant_type", "tenant_id", "activity_type"),
        CheckConstraint(
            "activity_type IN ("
            "'CREATED', 'STATUS_CHANGED', 'NOTE_ADDED', 'NOTE_UPDATED', "
            "'NOTE_DELETED', 'OWNER_CHANGED', 'CUSTOMER_LINKED', "
            "'SERVICE_LINKED', 'PRODUCT_LINKED', 'CONTACTED', 'BOOKED', "
            "'WON', 'LOST', 'CONVERTED', 'UPDATED', 'ARCHIVED', 'RESTORED'"
            ")",
            name="ck_lead_activities_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    lead: Mapped[Lead] = relationship(back_populates="activities")


class LeadConversion(Base):
    """Idempotent Lead → Customer conversion record. UNIQUE(tenant_id, lead_id)."""

    __tablename__ = "lead_conversions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "lead_id", name="uq_lead_conversions_tenant_lead"
        ),
        Index("ix_lead_conversions_tenant_id", "tenant_id"),
        Index("ix_lead_conversions_tenant_customer", "tenant_id", "customer_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_customer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    converted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    converted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    lead: Mapped[Lead] = relationship(back_populates="conversion")

"""Jobs and workforce ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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
from callbot_platform.db.models.crm import Customer
from callbot_platform.db.models.tenant import Tenant


class TenantUser(Base):
    __tablename__ = "tenant_users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_tenant_users_tenant_email"),
        Index("ix_tenant_users_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    technician: Mapped[Technician | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    job_notes: Mapped[list[JobNote]] = relationship(back_populates="author")


class Technician(Base):
    __tablename__ = "technicians"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_technicians_user_id"),
        Index("ix_technicians_tenant_id", "tenant_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_location_at: Mapped[datetime | None] = mapped_column(
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

    tenant: Mapped[Tenant] = relationship(back_populates="technicians")
    user: Mapped[TenantUser] = relationship(back_populates="technician")
    jobs: Mapped[list[Job]] = relationship(back_populates="assigned_technician")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_tenant_id", "tenant_id"),
        Index("ix_jobs_tenant_status", "tenant_id", "status"),
        Index("ix_jobs_tenant_created", "tenant_id", "created_at"),
        Index("ix_jobs_tenant_technician", "tenant_id", "assigned_technician_id"),
        UniqueConstraint(
            "tenant_id", "appointment_id", name="uq_jobs_tenant_appointment"
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
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    call_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True
    )
    assigned_technician_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    service_type: Mapped[str] = mapped_column(String(128), nullable=False)
    scheduled_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checklist: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    tenant: Mapped[Tenant] = relationship(back_populates="jobs")
    customer: Mapped[Customer] = relationship(back_populates="jobs")
    assigned_technician: Mapped[Technician | None] = relationship(back_populates="jobs")
    notes: Mapped[list[JobNote]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobNote(Base):
    __tablename__ = "job_notes"
    __table_args__ = (
        Index("ix_job_notes_tenant_id", "tenant_id"),
        Index("ix_job_notes_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
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

    job: Mapped[Job] = relationship(back_populates="notes")
    author: Mapped[TenantUser | None] = relationship(back_populates="job_notes")

"""Multi-profile agent configuration ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid

if TYPE_CHECKING:
    from callbot_platform.db.models.knowledge import KnowledgeArticle
    from callbot_platform.db.models.tenant import Tenant, TenantPhoneNumber


def default_enabled_tools() -> dict[str, bool]:
    return {
        "crm": True,
        "scheduling": True,
        "knowledge": True,
        "handoff": True,
        "sms": True,
    }


def default_business_hours() -> dict[str, list[list[str]]]:
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


class AgentProfile(Base):
    """Named agent configuration owned by a tenant (many per tenant)."""

    __tablename__ = "agent_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_agent_profiles_tenant_slug"),
        Index("ix_agent_profiles_tenant_id", "tenant_id"),
        Index("ix_agent_profiles_tenant_default", "tenant_id", "is_default"),
        Index("ix_agent_profiles_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="receptionist"
    )
    industry_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
    business_hours: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=default_business_hours
    )
    booking_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_disclosure_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    handoff_rules_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    restricted_topics: Mapped[list[Any]] = mapped_column(
        JsonType, nullable=False, default=list
    )
    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled_tools: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=default_enabled_tools
    )
    call_flow: Mapped[dict[str, Any] | None] = mapped_column(
        JsonType, nullable=True, default=None
    )
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

    tenant: Mapped[Tenant] = relationship(
        back_populates="agent_profiles",
        foreign_keys=[tenant_id],
    )
    phone_numbers: Mapped[list[TenantPhoneNumber]] = relationship(
        back_populates="agent_profile",
        foreign_keys="TenantPhoneNumber.agent_profile_id",
    )
    knowledge_articles: Mapped[list[KnowledgeArticle]] = relationship(
        back_populates="agent_profile",
        foreign_keys="KnowledgeArticle.agent_profile_id",
    )

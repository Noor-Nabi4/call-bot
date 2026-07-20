"""Knowledge base ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from callbot_platform.db.models.base import Base, JsonType, _utcnow, _uuid
from callbot_platform.db.models.tenant import Tenant


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        Index("ix_knowledge_articles_tenant_id", "tenant_id"),
        Index("ix_knowledge_articles_tenant_active", "tenant_id", "is_active"),
        Index("ix_knowledge_articles_agent_profile_id", "agent_profile_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="faq")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[Any]] = mapped_column(JsonType, nullable=False, default=list)
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

    tenant: Mapped[Tenant] = relationship(back_populates="knowledge_articles")
    agent_profile = relationship("AgentProfile", back_populates="knowledge_articles")

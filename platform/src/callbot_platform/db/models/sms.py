"""Phase 15 SMS conversation + message persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
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


class SmsConversation(Base):
    __tablename__ = "sms_conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "phone_e164",
            "business_phone_e164",
            name="uq_sms_conversations_tenant_phones",
        ),
        Index("ix_sms_conversations_tenant_phone", "tenant_id", "phone_e164"),
        Index("ix_sms_conversations_tenant_customer", "tenant_id", "customer_id"),
        Index("ix_sms_conversations_tenant_last_message", "tenant_id", "last_message_at"),
        CheckConstraint(
            "status IN ('ACTIVE','CLOSED','HANDOFF')",
            name="ck_sms_conversations_status",
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
    phone_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    business_phone_e164: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    workflow_state: Mapped[dict[str, Any]] = mapped_column(
        JsonType, nullable=False, default=dict
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
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

    messages: Mapped[list[SmsMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class SmsMessage(Base):
    __tablename__ = "sms_messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_sms_messages_tenant_provider_message",
        ),
        Index(
            "ix_sms_messages_tenant_conversation_created",
            "tenant_id",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_sms_messages_tenant_customer_created",
            "tenant_id",
            "customer_id",
            "created_at",
        ),
        Index("ix_sms_messages_tenant_provider", "tenant_id", "provider_message_id"),
        CheckConstraint(
            "direction IN ('INBOUND','OUTBOUND')",
            name="ck_sms_messages_direction",
        ),
        CheckConstraint(
            "status IN ("
            "'RECEIVED','PROCESSING','PROCESSED','FAILED',"
            "'QUEUED','SENT','DELIVERED'"
            ")",
            name="ck_sms_messages_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sms_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    sender_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECEIVED")
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    outbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_outbox.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JsonType, nullable=False, default=dict
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

    conversation: Mapped[SmsConversation] = relationship(back_populates="messages")

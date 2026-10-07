"""Phase 15 AI SMS Agent: conversations and inbound/outbound messages."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0044_sms_agent"
down_revision = "0043_estimates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phone_e164", sa.String(32), nullable=False),
        sa.Column("business_phone_e164", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "workflow_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE','CLOSED','HANDOFF')",
            name="ck_sms_conversations_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "phone_e164",
            "business_phone_e164",
            name="uq_sms_conversations_tenant_phones",
        ),
    )
    op.create_index(
        "ix_sms_conversations_tenant_phone",
        "sms_conversations",
        ["tenant_id", "phone_e164"],
    )
    op.create_index(
        "ix_sms_conversations_tenant_customer",
        "sms_conversations",
        ["tenant_id", "customer_id"],
    )
    op.create_index(
        "ix_sms_conversations_tenant_last_message",
        "sms_conversations",
        ["tenant_id", "last_message_at"],
    )

    op.create_table(
        "sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sms_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider_message_id", sa.String(128), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("sender_phone", sa.String(32), nullable=False),
        sa.Column("recipient_phone", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RECEIVED"),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "outbox_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_outbox.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('INBOUND','OUTBOUND')",
            name="ck_sms_messages_direction",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'RECEIVED','PROCESSING','PROCESSED','FAILED',"
            "'QUEUED','SENT','DELIVERED'"
            ")",
            name="ck_sms_messages_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_message_id",
            name="uq_sms_messages_tenant_provider_message",
        ),
    )
    op.create_index(
        "ix_sms_messages_tenant_conversation_created",
        "sms_messages",
        ["tenant_id", "conversation_id", "created_at"],
    )
    op.create_index(
        "ix_sms_messages_tenant_customer_created",
        "sms_messages",
        ["tenant_id", "customer_id", "created_at"],
    )
    op.create_index(
        "ix_sms_messages_tenant_provider",
        "sms_messages",
        ["tenant_id", "provider_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sms_messages_tenant_provider", table_name="sms_messages")
    op.drop_index(
        "ix_sms_messages_tenant_customer_created", table_name="sms_messages"
    )
    op.drop_index(
        "ix_sms_messages_tenant_conversation_created", table_name="sms_messages"
    )
    op.drop_table("sms_messages")
    op.drop_index(
        "ix_sms_conversations_tenant_last_message", table_name="sms_conversations"
    )
    op.drop_index(
        "ix_sms_conversations_tenant_customer", table_name="sms_conversations"
    )
    op.drop_index("ix_sms_conversations_tenant_phone", table_name="sms_conversations")
    op.drop_table("sms_conversations")

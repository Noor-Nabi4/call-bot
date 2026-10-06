"""Phase 2: outbox worker columns, recording objects, dequeue index."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0021_phase2_outbox_storage"
down_revision = "0020_tenancy_scaling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_outbox",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notification_outbox",
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column(
        "notification_outbox",
        "appointment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.alter_column("notification_outbox", "attempt_count", server_default=None)
    op.alter_column("notification_outbox", "payload", server_default=None)

    op.create_index(
        "ix_notification_outbox_dequeue",
        "notification_outbox",
        ["status", "next_attempt_at", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_notification_outbox_tenant_idempotency",
        "notification_outbox",
        ["tenant_id", "idempotency_key"],
        unique=True,
    )

    op.create_table(
        "recording_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="stored"),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_recording_objects_tenant_id", "recording_objects", ["tenant_id"]
    )
    op.create_index(
        "ix_recording_objects_tenant_retention",
        "recording_objects",
        ["tenant_id", "retention_until"],
    )
    op.create_index(
        "uq_recording_objects_tenant_key",
        "recording_objects",
        ["tenant_id", "object_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_recording_objects_tenant_key", table_name="recording_objects")
    op.drop_index(
        "ix_recording_objects_tenant_retention", table_name="recording_objects"
    )
    op.drop_index("ix_recording_objects_tenant_id", table_name="recording_objects")
    op.drop_table("recording_objects")

    op.drop_index(
        "uq_notification_outbox_tenant_idempotency",
        table_name="notification_outbox",
    )
    op.drop_index("ix_notification_outbox_dequeue", table_name="notification_outbox")
    op.drop_column("notification_outbox", "payload")
    op.drop_column("notification_outbox", "idempotency_key")
    op.drop_column("notification_outbox", "claimed_by")
    op.drop_column("notification_outbox", "claimed_at")
    op.drop_column("notification_outbox", "next_attempt_at")
    op.drop_column("notification_outbox", "attempt_count")
    op.alter_column(
        "notification_outbox",
        "appointment_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

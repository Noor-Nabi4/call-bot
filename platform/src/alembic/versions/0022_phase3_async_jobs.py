"""Phase 3: async jobs, lease reclaim, Stripe signup intent columns."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0022_phase3_async_jobs"
down_revision = "0021_phase2_outbox_storage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "async_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="pending"
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "result",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index(
        "uq_async_jobs_tenant_idempotency",
        "async_jobs",
        ["tenant_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_async_jobs_dequeue",
        "async_jobs",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_index(
        "ix_async_jobs_tenant_status", "async_jobs", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_async_jobs_job_type_status", "async_jobs", ["job_type", "status"]
    )
    op.create_index("ix_async_jobs_resource", "async_jobs", ["resource_id"])

    op.alter_column("async_jobs", "attempt_count", server_default=None)
    op.alter_column("async_jobs", "max_attempts", server_default=None)
    op.alter_column("async_jobs", "status", server_default=None)
    op.alter_column("async_jobs", "payload", server_default=None)
    op.alter_column("async_jobs", "result", server_default=None)

    op.add_column(
        "notification_outbox",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_outbox",
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Allow pending Stripe customer placeholder until saga completes.
    op.alter_column(
        "tenant_subscriptions",
        "stripe_customer_id",
        existing_type=sa.String(length=128),
        nullable=True,
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column("checkout_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_subscriptions",
        sa.Column(
            "provisioning_status",
            sa.String(length=32),
            nullable=False,
            server_default="ready",
        ),
    )
    op.alter_column("tenant_subscriptions", "provisioning_status", server_default=None)


def downgrade() -> None:
    op.drop_column("tenant_subscriptions", "provisioning_status")
    op.drop_column("tenant_subscriptions", "checkout_url")
    op.alter_column(
        "tenant_subscriptions",
        "stripe_customer_id",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.drop_column("notification_outbox", "last_failed_at")
    op.drop_column("notification_outbox", "first_failed_at")
    op.drop_column("notification_outbox", "lease_expires_at")

    op.drop_index("ix_async_jobs_resource", table_name="async_jobs")
    op.drop_index("ix_async_jobs_job_type_status", table_name="async_jobs")
    op.drop_index("ix_async_jobs_tenant_status", table_name="async_jobs")
    op.drop_index("ix_async_jobs_dequeue", table_name="async_jobs")
    op.drop_index("uq_async_jobs_tenant_idempotency", table_name="async_jobs")
    op.drop_table("async_jobs")

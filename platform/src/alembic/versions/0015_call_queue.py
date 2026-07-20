"""Add call_queue_items for handoff follow-up queue."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0015_call_queue"
down_revision = "0014_call_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_queue_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="waiting"),
        sa.Column("reason", sa.String(length=64), nullable=False, server_default="handoff"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("claimed_by", sa.String(length=255), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "call_id", name="uq_call_queue_items_tenant_call"
        ),
    )
    op.create_index(
        "ix_call_queue_items_tenant_id", "call_queue_items", ["tenant_id"]
    )
    op.create_index(
        "ix_call_queue_items_tenant_status",
        "call_queue_items",
        ["tenant_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_call_queue_items_tenant_status", table_name="call_queue_items")
    op.drop_index("ix_call_queue_items_tenant_id", table_name="call_queue_items")
    op.drop_table("call_queue_items")

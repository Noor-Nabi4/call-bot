"""Inventory outbox worker claim/retry columns.

Adds lease/retry fields to inventory_outbox_events so the domain outbox
can use the same claim → process → backoff pattern as notification_outbox.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0033_inventory_outbox_worker"
down_revision = "0032_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inventory_outbox_events",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("first_failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "inventory_outbox_events",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_inventory_outbox_dequeue",
        "inventory_outbox_events",
        ["status", "next_attempt_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_outbox_dequeue", table_name="inventory_outbox_events")
    op.drop_column("inventory_outbox_events", "updated_at")
    op.drop_column("inventory_outbox_events", "last_failed_at")
    op.drop_column("inventory_outbox_events", "first_failed_at")
    op.drop_column("inventory_outbox_events", "processed_at")
    op.drop_column("inventory_outbox_events", "lease_expires_at")
    op.drop_column("inventory_outbox_events", "claimed_by")
    op.drop_column("inventory_outbox_events", "claimed_at")
    op.drop_column("inventory_outbox_events", "next_attempt_at")
    op.drop_column("inventory_outbox_events", "attempt_count")

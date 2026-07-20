"""Add billable_seconds to calls for usage metering."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0011_usage_tracking"
down_revision = "0010_agent_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column("billable_seconds", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_calls_tenant_ended_at",
        "calls",
        ["tenant_id", "ended_at"],
        unique=False,
    )
    # Backfill closed calls from wall-clock duration (Postgres).
    op.execute(
        """
        UPDATE calls
        SET billable_seconds = CEIL(
            EXTRACT(EPOCH FROM (ended_at - started_at))
        )::integer
        WHERE ended_at IS NOT NULL
          AND billable_seconds IS NULL
          AND ended_at >= started_at
        """
    )


def downgrade() -> None:
    op.drop_index("ix_calls_tenant_ended_at", table_name="calls")
    op.drop_column("calls", "billable_seconds")

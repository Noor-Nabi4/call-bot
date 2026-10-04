"""Add call_cogs table for internal voice cost estimates."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018_call_cogs"
down_revision = "0017_tenant_branding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_cogs",
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("billable_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column(
            "transfer_kind",
            sa.String(length=16),
            nullable=False,
            server_default="none",
        ),
        sa.Column(
            "openai_cost_micros", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "livekit_agent_cost_micros",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "livekit_sip_cost_micros", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "livekit_bvc_cost_micros", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "twilio_origination_cost_micros",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "twilio_termination_cost_micros",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_estimated_cogs_micros",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "openai_cost_source",
            sa.String(length=32),
            nullable=False,
            server_default="per_minute_estimate",
        ),
        sa.Column(
            "openai_usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column(
            "rate_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("notes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
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
        "ix_call_cogs_tenant_id_created_at",
        "call_cogs",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_call_cogs_tenant_id_created_at", table_name="call_cogs")
    op.drop_table("call_cogs")

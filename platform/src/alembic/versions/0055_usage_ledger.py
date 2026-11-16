"""Phase 32 AI cost tracking: usage ledger + alert dedupe."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0055_usage_ledger"
down_revision = "0054_integrations"
branch_labels = None
depends_on = None

_USAGE_TYPES = (
    "VOICE_MINUTES",
    "LLM_INPUT_TOKENS",
    "LLM_OUTPUT_TOKENS",
    "AI_REQUESTS",
    "TOOL_CALLS",
    "SMS",
    "TRANSCRIPTION",
    "STORAGE",
    "INFRASTRUCTURE",
)


def upgrade() -> None:
    op.create_table(
        "usage_ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("usage_type", sa.String(32), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("billing_period", sa.String(7), nullable=False),
        sa.Column("pricing_version", sa.String(64), nullable=False),
        sa.Column("unit_cost_micros", sa.BigInteger(), nullable=True),
        sa.Column("total_cost_micros", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("cost_basis", sa.String(32), nullable=False, server_default="none"),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "usage_type IN (" + ",".join(f"'{t}'" for t in _USAGE_TYPES) + ")",
            name="ck_usage_ledger_entries_usage_type",
        ),
        sa.CheckConstraint(
            "cost_basis IN ('observed','configured','allocated','none')",
            name="ck_usage_ledger_entries_cost_basis",
        ),
        sa.CheckConstraint("quantity >= 0", name="ck_usage_ledger_entries_quantity"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_usage_ledger_entries_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_usage_ledger_tenant_type_occurred",
        "usage_ledger_entries",
        ["tenant_id", "usage_type", "occurred_at"],
    )
    op.create_index(
        "ix_usage_ledger_tenant_period",
        "usage_ledger_entries",
        ["tenant_id", "billing_period"],
    )
    op.create_index(
        "ix_usage_ledger_tenant_source",
        "usage_ledger_entries",
        ["tenant_id", "source_type", "source_id"],
    )

    op.create_table(
        "usage_alert_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_key", sa.String(64), nullable=False),
        sa.Column("threshold_pct", sa.Integer(), nullable=False),
        sa.Column("billing_period", sa.String(7), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False, server_default="outbox"),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint(
            "tenant_id",
            "alert_key",
            "threshold_pct",
            "billing_period",
            name="uq_usage_alert_deliveries_dedupe",
        ),
    )
    op.create_index(
        "ix_usage_alert_deliveries_tenant_period",
        "usage_alert_deliveries",
        ["tenant_id", "billing_period"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_usage_alert_deliveries_tenant_period", table_name="usage_alert_deliveries"
    )
    op.drop_table("usage_alert_deliveries")
    op.drop_index("ix_usage_ledger_tenant_source", table_name="usage_ledger_entries")
    op.drop_index("ix_usage_ledger_tenant_period", table_name="usage_ledger_entries")
    op.drop_index(
        "ix_usage_ledger_tenant_type_occurred", table_name="usage_ledger_entries"
    )
    op.drop_table("usage_ledger_entries")

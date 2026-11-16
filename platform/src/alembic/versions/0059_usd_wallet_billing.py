"""Internal USD wallet billing tables + subscription period fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "0059_usd_wallet_billing"
down_revision = "0058_geo_reference_catalogs"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    existing = _tables()

    if "wallets" not in existing:
        op.create_table(
            "wallets",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "currency", sa.String(length=3), nullable=False, server_default="USD"
            ),
            sa.Column(
                "available_balance_cents",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "reserved_balance_cents",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="ACTIVE"
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", name="uq_wallets_tenant"),
        )
        op.create_index("ix_wallets_status", "wallets", ["status"], unique=False)

    if "wallet_transactions" not in existing:
        op.create_table(
            "wallet_transactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("transaction_type", sa.String(length=16), nullable=False),
            sa.Column("amount_cents", sa.BigInteger(), nullable=False),
            sa.Column(
                "currency", sa.String(length=3), nullable=False, server_default="USD"
            ),
            sa.Column("balance_after_cents", sa.BigInteger(), nullable=False),
            sa.Column("reference_type", sa.String(length=32), nullable=True),
            sa.Column("reference_id", sa.String(length=128), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id",
                "idempotency_key",
                name="uq_wallet_transactions_tenant_idempotency",
            ),
        )
        op.create_index(
            "ix_wallet_transactions_wallet_created",
            "wallet_transactions",
            ["wallet_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_wallet_transactions_tenant_created",
            "wallet_transactions",
            ["tenant_id", "created_at"],
            unique=False,
        )

    if "wallet_topups" not in existing:
        op.create_table(
            "wallet_topups",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("amount_cents", sa.BigInteger(), nullable=False),
            sa.Column(
                "currency", sa.String(length=3), nullable=False, server_default="USD"
            ),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="PENDING"
            ),
            sa.Column("stripe_checkout_session_id", sa.String(length=128), nullable=True),
            sa.Column("stripe_payment_intent_id", sa.String(length=128), nullable=True),
            sa.Column("checkout_url", sa.Text(), nullable=True),
            sa.Column(
                "wallet_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
            ),
            sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["wallet_transaction_id"],
                ["wallet_transactions.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "stripe_checkout_session_id", name="uq_wallet_topups_checkout_session"
            ),
            sa.UniqueConstraint(
                "stripe_payment_intent_id", name="uq_wallet_topups_payment_intent"
            ),
        )
        op.create_index(
            "ix_wallet_topups_tenant_status",
            "wallet_topups",
            ["tenant_id", "status"],
            unique=False,
        )

    if "wallet_reservations" not in existing:
        op.create_table(
            "wallet_reservations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("amount_cents", sa.BigInteger(), nullable=False),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="OPEN"
            ),
            sa.Column("reference_type", sa.String(length=32), nullable=True),
            sa.Column("reference_id", sa.String(length=128), nullable=True),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id",
                "idempotency_key",
                name="uq_wallet_reservations_tenant_idempotency",
            ),
        )
        op.create_index(
            "ix_wallet_reservations_wallet_status",
            "wallet_reservations",
            ["wallet_id", "status"],
            unique=False,
        )

    if "wallet_settings" not in existing:
        op.create_table(
            "wallet_settings",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "low_balance_cents",
                sa.Integer(),
                nullable=False,
                server_default="2000",
            ),
            sa.Column(
                "critical_balance_cents",
                sa.Integer(),
                nullable=False,
                server_default="500",
            ),
            sa.Column(
                "auto_topup_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "auto_topup_threshold_cents",
                sa.Integer(),
                nullable=False,
                server_default="1000",
            ),
            sa.Column(
                "auto_topup_amount_cents",
                sa.Integer(),
                nullable=False,
                server_default="5000",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", name="uq_wallet_settings_tenant"),
        )

    if "usage_charges" not in existing:
        op.create_table(
            "usage_charges",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("call_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("billing_period", sa.String(length=16), nullable=False),
            sa.Column(
                "billable_seconds", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "billable_minutes", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "included_minutes_used",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "overage_minutes", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "rate_per_minute_cents",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "total_amount_cents",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "status", sa.String(length=16), nullable=False, server_default="PENDING"
            ),
            sa.Column(
                "wallet_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["wallet_transaction_id"],
                ["wallet_transactions.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id", "call_id", name="uq_usage_charges_tenant_call"
            ),
        )
        op.create_index(
            "ix_usage_charges_tenant_period",
            "usage_charges",
            ["tenant_id", "billing_period"],
            unique=False,
        )

    sub_cols = [
        ("billing_period_start", sa.Column("billing_period_start", sa.DateTime(timezone=True), nullable=True)),
        ("billing_period_end", sa.Column("billing_period_end", sa.DateTime(timezone=True), nullable=True)),
        ("next_billing_at", sa.Column("next_billing_at", sa.DateTime(timezone=True), nullable=True)),
        ("monthly_price_cents", sa.Column("monthly_price_cents", sa.Integer(), nullable=True)),
        ("included_minutes", sa.Column("included_minutes", sa.Integer(), nullable=True)),
        ("overage_rate_cents", sa.Column("overage_rate_cents", sa.Integer(), nullable=True)),
        (
            "included_minutes_consumed",
            sa.Column(
                "included_minutes_consumed",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        ),
        (
            "grace_period_ends_at",
            sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        ),
    ]
    for name, col in sub_cols:
        if not _has_column("tenant_subscriptions", name):
            op.add_column("tenant_subscriptions", col)


def downgrade() -> None:
    existing = _tables()
    for name in (
        "grace_period_ends_at",
        "included_minutes_consumed",
        "overage_rate_cents",
        "included_minutes",
        "monthly_price_cents",
        "next_billing_at",
        "billing_period_end",
        "billing_period_start",
    ):
        if _has_column("tenant_subscriptions", name):
            op.drop_column("tenant_subscriptions", name)

    if "usage_charges" in existing:
        op.drop_index("ix_usage_charges_tenant_period", table_name="usage_charges")
        op.drop_table("usage_charges")
    if "wallet_settings" in existing:
        op.drop_table("wallet_settings")
    if "wallet_reservations" in existing:
        op.drop_index(
            "ix_wallet_reservations_wallet_status", table_name="wallet_reservations"
        )
        op.drop_table("wallet_reservations")
    if "wallet_topups" in existing:
        op.drop_index("ix_wallet_topups_tenant_status", table_name="wallet_topups")
        op.drop_table("wallet_topups")
    if "wallet_transactions" in existing:
        op.drop_index(
            "ix_wallet_transactions_tenant_created", table_name="wallet_transactions"
        )
        op.drop_index(
            "ix_wallet_transactions_wallet_created", table_name="wallet_transactions"
        )
        op.drop_table("wallet_transactions")
    if "wallets" in existing:
        op.drop_index("ix_wallets_status", table_name="wallets")
        op.drop_table("wallets")

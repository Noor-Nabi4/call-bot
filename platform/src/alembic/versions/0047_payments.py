"""Phase 19 Payments: Stripe invoice payments, refunds, unique payment application."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0047_payments"
down_revision = "0046_invoicing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="stripe"),
        sa.Column("provider_checkout_session_id", sa.String(128), nullable=True),
        sa.Column("provider_payment_intent_id", sa.String(128), nullable=True),
        sa.Column("provider_charge_id", sa.String(128), nullable=True),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("payment_method_type", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column(
            "refunded_amount", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column(
            "applied_to_invoice", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("idempotency_request_hash", sa.String(64), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_payments_tenant_idempotency"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_checkout_session_id",
            name="uq_payments_tenant_checkout_session",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_payment_intent_id",
            name="uq_payments_tenant_payment_intent",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'PENDING','PROCESSING','SUCCEEDED','FAILED',"
            "'CANCELLED','REFUNDED','PARTIALLY_REFUNDED'"
            ")",
            name="ck_payments_status",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint(
            "refunded_amount >= 0", name="ck_payments_refunded_nonneg"
        ),
        sa.CheckConstraint("provider IN ('stripe')", name="ck_payments_provider"),
    )
    op.create_index("ix_payments_tenant_status", "payments", ["tenant_id", "status"])
    op.create_index(
        "ix_payments_tenant_invoice", "payments", ["tenant_id", "invoice_id"]
    )
    op.create_index(
        "ix_payments_tenant_customer", "payments", ["tenant_id", "customer_id"]
    )
    op.create_index(
        "ix_payments_tenant_created", "payments", ["tenant_id", "created_at"]
    )

    op.create_table(
        "payment_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("provider_refund_id", sa.String(128), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_payment_refunds_tenant_idempotency",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_refund_id",
            name="uq_payment_refunds_tenant_provider_refund",
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_refunds_amount_positive"),
        sa.CheckConstraint(
            "status IN ('PENDING','SUCCEEDED','FAILED')",
            name="ck_payment_refunds_status",
        ),
    )
    op.create_index(
        "ix_payment_refunds_tenant_payment",
        "payment_refunds",
        ["tenant_id", "payment_id"],
    )

def downgrade() -> None:
    op.drop_index(
        "ix_payment_refunds_tenant_payment", table_name="payment_refunds"
    )
    op.drop_table("payment_refunds")
    op.drop_index("ix_payments_tenant_created", table_name="payments")
    op.drop_index("ix_payments_tenant_customer", table_name="payments")
    op.drop_index("ix_payments_tenant_invoice", table_name="payments")
    op.drop_index("ix_payments_tenant_status", table_name="payments")
    op.drop_table("payments")

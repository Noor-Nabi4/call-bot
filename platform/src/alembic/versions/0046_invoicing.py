"""Phase 18 Invoicing: invoices, items, status history, payment applications."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0046_invoicing"
down_revision = "0045_knowledge_rag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_number_counters",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_invoice_number_counters_tenant"),
    )

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("invoice_number", sa.String(32), nullable=False),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("estimates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "discount_amount", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column(
            "invoice_discount", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("tax_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "total_amount", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("amount_paid", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("idempotency_request_hash", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "invoice_number", name="uq_invoices_tenant_invoice_number"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_invoices_tenant_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SENT','PARTIALLY_PAID','PAID','OVERDUE','VOID')",
            name="ck_invoices_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_nonneg"),
        sa.CheckConstraint(
            "discount_amount >= 0", name="ck_invoices_discount_nonneg"
        ),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoices_tax_nonneg"),
        sa.CheckConstraint("total_amount >= 0", name="ck_invoices_total_nonneg"),
        sa.CheckConstraint("amount_paid >= 0", name="ck_invoices_amount_paid_nonneg"),
        sa.CheckConstraint("balance_due >= 0", name="ck_invoices_balance_nonneg"),
    )
    op.create_index("ix_invoices_tenant_status", "invoices", ["tenant_id", "status"])
    op.create_index(
        "ix_invoices_tenant_customer", "invoices", ["tenant_id", "customer_id"]
    )
    op.create_index(
        "ix_invoices_tenant_due_date", "invoices", ["tenant_id", "due_date"]
    )
    op.create_index(
        "ix_invoices_tenant_created", "invoices", ["tenant_id", "created_at"]
    )
    op.create_index("ix_invoices_tenant_job", "invoices", ["tenant_id", "job_id"])
    op.create_index("ix_invoices_tenant_order", "invoices", ["tenant_id", "order_id"])
    op.create_index(
        "ix_invoices_tenant_number", "invoices", ["tenant_id", "invoice_number"]
    )

    op.create_table(
        "invoice_items",
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
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(16), nullable=False),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(19, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(19, 4), nullable=False),
        sa.Column(
            "discount_amount", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("tax_amount", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("line_subtotal", sa.Numeric(19, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(19, 4), nullable=False),
        sa.Column("pricing_source_snapshot", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('SERVICE','PRODUCT','CUSTOM')",
            name="ck_invoice_items_type",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_items_quantity_positive"),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_invoice_items_unit_price_nonneg"
        ),
        sa.CheckConstraint(
            "discount_amount >= 0", name="ck_invoice_items_discount_nonneg"
        ),
        sa.CheckConstraint("tax_amount >= 0", name="ck_invoice_items_tax_nonneg"),
        sa.CheckConstraint(
            "line_subtotal >= 0", name="ck_invoice_items_subtotal_nonneg"
        ),
        sa.CheckConstraint("line_total >= 0", name="ck_invoice_items_total_nonneg"),
    )
    op.create_index(
        "ix_invoice_items_tenant_invoice",
        "invoice_items",
        ["tenant_id", "invoice_id"],
    )

    op.create_table(
        "invoice_status_history",
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
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("actor_type", sa.String(64), nullable=True),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_invoice_status_history_tenant_invoice",
        "invoice_status_history",
        ["tenant_id", "invoice_id"],
    )
    op.create_index(
        "ix_invoice_status_history_tenant_created",
        "invoice_status_history",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "invoice_payment_applications",
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
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("amount", sa.Numeric(19, 4), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("reference_note", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_invoice_payment_apps_tenant_idempotency",
        ),
        sa.CheckConstraint("amount > 0", name="ck_invoice_payment_apps_amount_positive"),
    )
    op.create_index(
        "ix_invoice_payment_apps_tenant_invoice",
        "invoice_payment_applications",
        ["tenant_id", "invoice_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_payment_apps_tenant_invoice",
        table_name="invoice_payment_applications",
    )
    op.drop_table("invoice_payment_applications")
    op.drop_index(
        "ix_invoice_status_history_tenant_created",
        table_name="invoice_status_history",
    )
    op.drop_index(
        "ix_invoice_status_history_tenant_invoice",
        table_name="invoice_status_history",
    )
    op.drop_table("invoice_status_history")
    op.drop_index("ix_invoice_items_tenant_invoice", table_name="invoice_items")
    op.drop_table("invoice_items")
    op.drop_index("ix_invoices_tenant_number", table_name="invoices")
    op.drop_index("ix_invoices_tenant_order", table_name="invoices")
    op.drop_index("ix_invoices_tenant_job", table_name="invoices")
    op.drop_index("ix_invoices_tenant_created", table_name="invoices")
    op.drop_index("ix_invoices_tenant_due_date", table_name="invoices")
    op.drop_index("ix_invoices_tenant_customer", table_name="invoices")
    op.drop_index("ix_invoices_tenant_status", table_name="invoices")
    op.drop_table("invoices")
    op.drop_table("invoice_number_counters")

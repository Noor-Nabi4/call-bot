"""Phase 13 Estimates: quotes, line items, status history, conversions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0043_estimates"
down_revision = "0042_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estimate_number_counters",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_estimate_number_counters_tenant"),
    )

    op.create_table(
        "estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("estimate_number", sa.String(32), nullable=False),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False, server_default="Estimate"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("subtotal", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "discount_total", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("tax_total", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "estimate_discount", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column(
            "pricebook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pricebooks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.String(255), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("idempotency_request_hash", sa.String(64), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "estimate_number", name="uq_estimates_tenant_estimate_number"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_estimates_tenant_idempotency"
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SENT','VIEWED','APPROVED','REJECTED',"
            "'EXPIRED','CANCELLED','CONVERTED')",
            name="ck_estimates_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_estimates_subtotal_nonneg"),
        sa.CheckConstraint(
            "discount_total >= 0", name="ck_estimates_discount_nonneg"
        ),
        sa.CheckConstraint("tax_total >= 0", name="ck_estimates_tax_nonneg"),
        sa.CheckConstraint("total >= 0", name="ck_estimates_total_nonneg"),
    )
    op.create_index("ix_estimates_tenant_id", "estimates", ["tenant_id"])
    op.create_index(
        "ix_estimates_tenant_status", "estimates", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_estimates_tenant_customer", "estimates", ["tenant_id", "customer_id"]
    )
    op.create_index(
        "ix_estimates_tenant_created", "estimates", ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_estimates_tenant_archived", "estimates", ["tenant_id", "archived_at"]
    )
    op.create_index(
        "ix_estimates_tenant_valid_until", "estimates", ["tenant_id", "valid_until"]
    )
    op.create_index(
        "ix_estimates_tenant_number", "estimates", ["tenant_id", "estimate_number"]
    )

    op.create_table(
        "estimate_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("estimates.id", ondelete="CASCADE"),
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
        sa.Column(
            "pricebook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pricebooks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name_snapshot", sa.String(255), nullable=False),
        sa.Column("description_snapshot", sa.Text(), nullable=True),
        sa.Column("sku_snapshot", sa.String(64), nullable=True),
        sa.Column("code_snapshot", sa.String(64), nullable=True),
        sa.Column("pricing_source_snapshot", sa.String(64), nullable=True),
        sa.Column("tax_rate_snapshot", sa.Numeric(9, 4), nullable=True),
        sa.Column("quantity", sa.Numeric(19, 4), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(19, 4), nullable=False),
        sa.Column(
            "discount_total", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("tax_total", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("line_subtotal", sa.Numeric(19, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(19, 4), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('SERVICE','PRODUCT','CUSTOM')",
            name="ck_estimate_items_type",
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_estimate_items_quantity_positive"
        ),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_estimate_items_unit_price_nonneg"
        ),
        sa.CheckConstraint(
            "discount_total >= 0", name="ck_estimate_items_discount_nonneg"
        ),
        sa.CheckConstraint(
            "tax_total >= 0", name="ck_estimate_items_tax_nonneg"
        ),
        sa.CheckConstraint(
            "line_subtotal >= 0", name="ck_estimate_items_subtotal_nonneg"
        ),
        sa.CheckConstraint(
            "line_total >= 0", name="ck_estimate_items_total_nonneg"
        ),
    )
    op.create_index(
        "ix_estimate_items_tenant_estimate",
        "estimate_items",
        ["tenant_id", "estimate_id"],
    )
    op.create_index(
        "ix_estimate_items_tenant_product",
        "estimate_items",
        ["tenant_id", "product_id"],
    )
    op.create_index(
        "ix_estimate_items_tenant_service",
        "estimate_items",
        ["tenant_id", "service_id"],
    )

    op.create_table(
        "estimate_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("estimates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("changed_by", sa.String(255), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_estimate_status_history_tenant_estimate",
        "estimate_status_history",
        ["tenant_id", "estimate_id"],
    )
    op.create_index(
        "ix_estimate_status_history_tenant_created",
        "estimate_status_history",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "estimate_conversions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("estimates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_number", sa.String(32), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("idempotency_request_hash", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "estimate_id",
            name="uq_estimate_conversions_tenant_estimate",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_estimate_conversions_tenant_idempotency",
        ),
        sa.CheckConstraint(
            "target_type IN ('JOB','ORDER')",
            name="ck_estimate_conversions_target_type",
        ),
    )
    op.create_index(
        "ix_estimate_conversions_tenant_target",
        "estimate_conversions",
        ["tenant_id", "target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_estimate_conversions_tenant_target", table_name="estimate_conversions"
    )
    op.drop_table("estimate_conversions")
    op.drop_index(
        "ix_estimate_status_history_tenant_created",
        table_name="estimate_status_history",
    )
    op.drop_index(
        "ix_estimate_status_history_tenant_estimate",
        table_name="estimate_status_history",
    )
    op.drop_table("estimate_status_history")
    op.drop_index("ix_estimate_items_tenant_service", table_name="estimate_items")
    op.drop_index("ix_estimate_items_tenant_product", table_name="estimate_items")
    op.drop_index("ix_estimate_items_tenant_estimate", table_name="estimate_items")
    op.drop_table("estimate_items")
    op.drop_index("ix_estimates_tenant_number", table_name="estimates")
    op.drop_index("ix_estimates_tenant_valid_until", table_name="estimates")
    op.drop_index("ix_estimates_tenant_archived", table_name="estimates")
    op.drop_index("ix_estimates_tenant_created", table_name="estimates")
    op.drop_index("ix_estimates_tenant_customer", table_name="estimates")
    op.drop_index("ix_estimates_tenant_status", table_name="estimates")
    op.drop_index("ix_estimates_tenant_id", table_name="estimates")
    op.drop_table("estimates")
    op.drop_table("estimate_number_counters")

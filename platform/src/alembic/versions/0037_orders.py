"""Phase 9 Orders domain: orders, order_items, status history, number counters."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0037_orders"
down_revision = "0036_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_pg else sa.String(36)
    json_type = postgresql.JSONB() if is_pg else sa.JSON()

    op.create_table(
        "order_number_counters",
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("tenant_id", name="uq_order_number_counters_tenant"),
    )

    op.create_table(
        "orders",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("order_number", sa.String(length=32), nullable=False),
        sa.Column("customer_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("subtotal", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "discount_total", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("tax_total", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column(
            "shipping_total", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("total", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("shipping_address_snapshot", json_type, nullable=True),
        sa.Column("billing_address_snapshot", json_type, nullable=True),
        sa.Column("fulfillment_location_id", uuid_type, nullable=True),
        sa.Column(
            "inventory_reserved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
        sa.Column(
            "inventory_consumed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false") if is_pg else sa.text("0"),
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PENDING', 'CONFIRMED', 'PROCESSING', "
            "'SHIPPED', 'DELIVERED', 'CANCELLED', 'REFUNDED')",
            name="ck_orders_status",
        ),
        sa.CheckConstraint("subtotal >= 0", name="ck_orders_subtotal_nonneg"),
        sa.CheckConstraint("discount_total >= 0", name="ck_orders_discount_nonneg"),
        sa.CheckConstraint("tax_total >= 0", name="ck_orders_tax_nonneg"),
        sa.CheckConstraint("shipping_total >= 0", name="ck_orders_shipping_nonneg"),
        sa.CheckConstraint("total >= 0", name="ck_orders_total_nonneg"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["fulfillment_location_id"],
            ["inventory_locations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "order_number", name="uq_orders_tenant_order_number"
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_orders_tenant_idempotency"
        ),
    )
    op.create_index("ix_orders_tenant_id", "orders", ["tenant_id"])
    op.create_index("ix_orders_tenant_status", "orders", ["tenant_id", "status"])
    op.create_index(
        "ix_orders_tenant_customer", "orders", ["tenant_id", "customer_id"]
    )
    op.create_index("ix_orders_tenant_created", "orders", ["tenant_id", "created_at"])
    op.create_index(
        "ix_orders_tenant_archived", "orders", ["tenant_id", "archived_at"]
    )
    op.create_index(
        "ix_orders_tenant_number", "orders", ["tenant_id", "order_number"]
    )

    op.create_table(
        "order_items",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("order_id", uuid_type, nullable=False),
        sa.Column("product_id", uuid_type, nullable=False),
        sa.Column("variant_id", uuid_type, nullable=True),
        sa.Column("sku_snapshot", sa.String(length=64), nullable=False),
        sa.Column("product_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("variant_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("unit_price", sa.Numeric(19, 4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "discount_total", sa.Numeric(19, 4), nullable=False, server_default="0"
        ),
        sa.Column("tax_total", sa.Numeric(19, 4), nullable=False, server_default="0"),
        sa.Column("line_subtotal", sa.Numeric(19, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(19, 4), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.CheckConstraint(
            "unit_price >= 0", name="ck_order_items_unit_price_nonneg"
        ),
        sa.CheckConstraint(
            "discount_total >= 0", name="ck_order_items_discount_nonneg"
        ),
        sa.CheckConstraint("tax_total >= 0", name="ck_order_items_tax_nonneg"),
        sa.CheckConstraint(
            "line_subtotal >= 0", name="ck_order_items_subtotal_nonneg"
        ),
        sa.CheckConstraint("line_total >= 0", name="ck_order_items_total_nonneg"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["product_variants.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_items_tenant_order", "order_items", ["tenant_id", "order_id"]
    )
    op.create_index(
        "ix_order_items_tenant_product", "order_items", ["tenant_id", "product_id"]
    )
    op.create_index(
        "ix_order_items_tenant_variant", "order_items", ["tenant_id", "variant_id"]
    )
    op.create_index(
        "ix_order_items_tenant_sku", "order_items", ["tenant_id", "sku_snapshot"]
    )

    op.create_table(
        "order_status_history",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("order_id", uuid_type, nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("metadata", json_type, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_status_history_tenant_order",
        "order_status_history",
        ["tenant_id", "order_id"],
    )
    op.create_index(
        "ix_order_status_history_tenant_created",
        "order_status_history",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("order_status_history")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("order_number_counters")

"""Phase 7 Services & Pricebook domain."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0034_services_pricebook"
down_revision = "0033_inventory_outbox_worker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.create_table(
        "service_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "tenant_id", "slug", name="uq_service_categories_tenant_slug"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_service_categories_status",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_service_categories_no_self_parent",
        ),
    )
    op.create_index(
        "ix_service_categories_tenant_id", "service_categories", ["tenant_id"]
    )
    op.create_index(
        "ix_service_categories_tenant_parent",
        "service_categories",
        ["tenant_id", "parent_id"],
    )
    op.create_index(
        "ix_service_categories_tenant_archived",
        "service_categories",
        ["tenant_id", "archived_at"],
    )
    op.create_index(
        "ix_service_categories_tenant_status",
        "service_categories",
        ["tenant_id", "status"],
    )

    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("code_normalized", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("base_price", sa.Numeric(19, 4), nullable=True),
        sa.Column("cost", sa.Numeric(19, 4), nullable=True),
        sa.Column("tax_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "pricing_type",
            sa.String(length=32),
            nullable=False,
            server_default="FIXED",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_services_status",
        ),
        sa.CheckConstraint(
            "pricing_type IN ('FIXED', 'STARTING_AT', 'HOURLY', 'CUSTOM_QUOTE')",
            name="ck_services_pricing_type",
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_services_duration_positive",
        ),
        sa.CheckConstraint(
            "base_price IS NULL OR base_price >= 0",
            name="ck_services_base_price_nonneg",
        ),
        sa.CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_services_cost_nonneg",
        ),
        sa.CheckConstraint(
            "tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 100)",
            name="ck_services_tax_rate",
        ),
    )
    op.create_index("ix_services_tenant_id", "services", ["tenant_id"])
    op.create_index("ix_services_tenant_status", "services", ["tenant_id", "status"])
    op.create_index(
        "ix_services_tenant_archived", "services", ["tenant_id", "archived_at"]
    )
    op.create_index(
        "ix_services_tenant_category", "services", ["tenant_id", "category_id"]
    )
    op.create_index("ix_services_tenant_name", "services", ["tenant_id", "name"])
    op.create_index(
        "ix_services_tenant_code_normalized",
        "services",
        ["tenant_id", "code_normalized"],
    )
    if is_pg:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_services_tenant_code_active "
                "ON services (tenant_id, code_normalized) "
                "WHERE code_normalized IS NOT NULL AND archived_at IS NULL"
            )
        )
    else:
        op.create_index(
            "uq_services_tenant_code_active",
            "services",
            ["tenant_id", "code_normalized"],
            unique=True,
            sqlite_where=sa.text("code_normalized IS NOT NULL AND archived_at IS NULL"),
        )

    op.create_table(
        "pricebooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("tenant_id", "name", name="uq_pricebooks_tenant_name"),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_pricebooks_status",
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_pricebooks_effective_range",
        ),
    )
    op.create_index("ix_pricebooks_tenant_id", "pricebooks", ["tenant_id"])
    op.create_index(
        "ix_pricebooks_tenant_status", "pricebooks", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_pricebooks_tenant_archived", "pricebooks", ["tenant_id", "archived_at"]
    )
    op.create_index(
        "ix_pricebooks_tenant_default", "pricebooks", ["tenant_id", "is_default"]
    )
    op.create_index(
        "ix_pricebooks_tenant_effective",
        "pricebooks",
        ["tenant_id", "effective_from"],
    )
    if is_pg:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_pricebooks_tenant_one_default "
                "ON pricebooks (tenant_id) "
                "WHERE is_default = true AND archived_at IS NULL"
            )
        )
    else:
        op.create_index(
            "uq_pricebooks_tenant_one_default",
            "pricebooks",
            ["tenant_id"],
            unique=True,
            sqlite_where=sa.text("is_default = 1 AND archived_at IS NULL"),
        )

    op.create_table(
        "pricebook_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pricebook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pricebooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pricing_type", sa.String(length=32), nullable=False),
        sa.Column("price", sa.Numeric(19, 4), nullable=True),
        sa.Column("starting_price", sa.Numeric(19, 4), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(19, 4), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_pricebook_items_status",
        ),
        sa.CheckConstraint(
            "pricing_type IN ('FIXED', 'STARTING_AT', 'HOURLY', 'CUSTOM_QUOTE')",
            name="ck_pricebook_items_pricing_type",
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_pricebook_items_price_nonneg",
        ),
        sa.CheckConstraint(
            "starting_price IS NULL OR starting_price >= 0",
            name="ck_pricebook_items_starting_nonneg",
        ),
        sa.CheckConstraint(
            "hourly_rate IS NULL OR hourly_rate >= 0",
            name="ck_pricebook_items_hourly_nonneg",
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_pricebook_items_effective_range",
        ),
    )
    op.create_index("ix_pricebook_items_tenant_id", "pricebook_items", ["tenant_id"])
    op.create_index(
        "ix_pricebook_items_tenant_pricebook",
        "pricebook_items",
        ["tenant_id", "pricebook_id"],
    )
    op.create_index(
        "ix_pricebook_items_tenant_service",
        "pricebook_items",
        ["tenant_id", "service_id"],
    )
    op.create_index(
        "ix_pricebook_items_tenant_effective",
        "pricebook_items",
        ["tenant_id", "effective_from", "effective_until"],
    )
    op.create_index(
        "ix_pricebook_items_tenant_status",
        "pricebook_items",
        ["tenant_id", "status"],
    )

    op.create_table(
        "pricebook_item_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pricebook_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pricebook_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("component_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "product_variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "quantity",
            sa.Numeric(16, 4),
            nullable=False,
            server_default="1",
        ),
        sa.Column("unit_price", sa.Numeric(19, 4), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
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
        sa.CheckConstraint(
            "component_type IN ('LABOR', 'MATERIAL')",
            name="ck_pb_item_components_type",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_pb_item_components_quantity_positive",
        ),
        sa.CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_pb_item_components_unit_price_nonneg",
        ),
        sa.CheckConstraint(
            "(component_type = 'MATERIAL' AND product_variant_id IS NOT NULL) "
            "OR (component_type = 'LABOR')",
            name="ck_pb_item_components_material_variant",
        ),
    )
    op.create_index(
        "ix_pb_item_components_tenant_id",
        "pricebook_item_components",
        ["tenant_id"],
    )
    op.create_index(
        "ix_pb_item_components_tenant_item",
        "pricebook_item_components",
        ["tenant_id", "pricebook_item_id"],
    )
    op.create_index(
        "ix_pb_item_components_tenant_variant",
        "pricebook_item_components",
        ["tenant_id", "product_variant_id"],
    )

    op.create_table(
        "pricebook_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "pricebook_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pricebooks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("override_price", sa.Numeric(19, 4), nullable=True),
        sa.Column("pricing_type", sa.String(length=32), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_pricebook_overrides_status",
        ),
        sa.CheckConstraint(
            "pricing_type IS NULL OR pricing_type IN "
            "('FIXED', 'STARTING_AT', 'HOURLY', 'CUSTOM_QUOTE')",
            name="ck_pricebook_overrides_pricing_type",
        ),
        sa.CheckConstraint(
            "override_price IS NULL OR override_price >= 0",
            name="ck_pricebook_overrides_price_nonneg",
        ),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL "
            "OR effective_until >= effective_from",
            name="ck_pricebook_overrides_effective_range",
        ),
    )
    op.create_index(
        "ix_pricebook_overrides_tenant_id", "pricebook_overrides", ["tenant_id"]
    )
    op.create_index(
        "ix_pricebook_overrides_tenant_lookup",
        "pricebook_overrides",
        ["tenant_id", "pricebook_id", "service_id"],
    )
    op.create_index(
        "ix_pricebook_overrides_tenant_effective",
        "pricebook_overrides",
        ["tenant_id", "effective_from", "effective_until"],
    )


def downgrade() -> None:
    op.drop_table("pricebook_overrides")
    op.drop_table("pricebook_item_components")
    op.drop_table("pricebook_items")
    op.drop_index("uq_pricebooks_tenant_one_default", table_name="pricebooks")
    op.drop_table("pricebooks")
    op.drop_index("uq_services_tenant_code_active", table_name="services")
    op.drop_table("services")
    op.drop_table("service_categories")

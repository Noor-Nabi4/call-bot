"""Phase 5 Product Catalog tables.

Implementation-gate override: local schema only. Staging/production readiness remains
blocked (see docs/PRODUCTION_READINESS.md).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0031_product_catalog"
down_revision = "0030_customer_crm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.create_table(
        "product_brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("name_normalized", sa.String(length=128), nullable=False),
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
            "tenant_id", "name_normalized", name="uq_product_brands_tenant_name"
        ),
    )
    op.create_index("ix_product_brands_tenant_id", "product_brands", ["tenant_id"])

    op.create_table(
        "product_categories",
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
            sa.ForeignKey("product_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
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
            "tenant_id", "slug", name="uq_product_categories_tenant_slug"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_product_categories_status",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id",
            name="ck_product_categories_no_self_parent",
        ),
    )
    op.create_index(
        "ix_product_categories_tenant_id", "product_categories", ["tenant_id"]
    )
    op.create_index(
        "ix_product_categories_tenant_parent",
        "product_categories",
        ["tenant_id", "parent_id"],
    )
    op.create_index(
        "ix_product_categories_tenant_archived",
        "product_categories",
        ["tenant_id", "archived_at"],
    )

    op.create_table(
        "catalog_skus",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("sku_normalized", sa.String(length=64), nullable=False),
        sa.Column("owner_kind", sa.String(length=16), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "sku_normalized", name="uq_catalog_skus_tenant"
        ),
        sa.CheckConstraint(
            "owner_kind IN ('product', 'variant')",
            name="ck_catalog_skus_owner_kind",
        ),
    )
    op.create_index(
        "ix_catalog_skus_tenant_owner",
        "catalog_skus",
        ["tenant_id", "owner_kind", "owner_id"],
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=True),
        sa.Column("sku_normalized", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("price", sa.Numeric(19, 4), nullable=True),
        sa.Column("cost", sa.Numeric(19, 4), nullable=True),
        sa.Column("tax_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("weight", sa.Numeric(16, 4), nullable=True),
        sa.Column("weight_unit", sa.String(length=8), nullable=True),
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
            "status IN ('ACTIVE', 'INACTIVE')", name="ck_products_status"
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0", name="ck_products_price_nonneg"
        ),
        sa.CheckConstraint("cost IS NULL OR cost >= 0", name="ck_products_cost_nonneg"),
        sa.CheckConstraint(
            "tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 100)",
            name="ck_products_tax_rate",
        ),
        sa.CheckConstraint(
            "weight IS NULL OR weight >= 0", name="ck_products_weight_nonneg"
        ),
        sa.CheckConstraint(
            "weight_unit IS NULL OR weight_unit IN ('KG', 'G', 'LB', 'OZ')",
            name="ck_products_weight_unit",
        ),
    )
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])
    op.create_index("ix_products_tenant_status", "products", ["tenant_id", "status"])
    op.create_index(
        "ix_products_tenant_archived", "products", ["tenant_id", "archived_at"]
    )
    op.create_index(
        "ix_products_tenant_category", "products", ["tenant_id", "category_id"]
    )
    op.create_index("ix_products_tenant_brand", "products", ["tenant_id", "brand_id"])
    op.create_index("ix_products_tenant_name", "products", ["tenant_id", "name"])
    op.create_index(
        "ix_products_tenant_sku_normalized",
        "products",
        ["tenant_id", "sku_normalized"],
    )

    op.create_table(
        "product_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("name_normalized", sa.String(length=64), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "product_id",
            "name_normalized",
            name="uq_product_attributes_name",
        ),
    )
    op.create_index(
        "ix_product_attributes_tenant_product",
        "product_attributes",
        ["tenant_id", "product_id"],
    )

    op.create_table(
        "product_attribute_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attribute_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_attributes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=128), nullable=False),
        sa.Column("value_normalized", sa.String(length=128), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "attribute_id",
            "value_normalized",
            name="uq_product_attribute_values",
        ),
    )
    op.create_index(
        "ix_product_attribute_values_tenant_attr",
        "product_attribute_values",
        ["tenant_id", "attribute_id"],
    )

    op.create_table(
        "product_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("sku_normalized", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Numeric(19, 4), nullable=True),
        sa.Column("cost", sa.Numeric(19, 4), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("stock_on_hand", sa.Integer(), nullable=True),
        sa.Column("inventory_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "attribute_fingerprint",
            sa.String(length=512),
            nullable=False,
            server_default="",
        ),
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
            name="ck_product_variants_status",
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_product_variants_price_nonneg",
        ),
        sa.CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_product_variants_cost_nonneg",
        ),
        sa.CheckConstraint(
            "stock_on_hand IS NULL OR stock_on_hand >= 0",
            name="ck_product_variants_stock_nonneg",
        ),
    )
    op.create_index(
        "ix_product_variants_tenant_product",
        "product_variants",
        ["tenant_id", "product_id"],
    )
    op.create_index(
        "ix_product_variants_tenant_sku",
        "product_variants",
        ["tenant_id", "sku_normalized"],
    )
    if is_pg:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_product_variants_fingerprint "
                "ON product_variants (tenant_id, product_id, attribute_fingerprint) "
                "WHERE archived_at IS NULL"
            )
        )
    else:
        op.create_index(
            "uq_product_variants_fingerprint",
            "product_variants",
            ["tenant_id", "product_id", "attribute_fingerprint"],
            unique=True,
            sqlite_where=sa.text("archived_at IS NULL"),
        )

    op.create_table(
        "product_variant_attribute_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attribute_value_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_attribute_values.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "variant_id",
            "attribute_value_id",
            name="uq_variant_attr_value",
        ),
    )
    op.create_index(
        "ix_variant_attr_values_tenant_variant",
        "product_variant_attribute_values",
        ["tenant_id", "variant_id"],
    )

    op.create_table(
        "product_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column(
            "file_size", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "storage_backend",
            sa.String(length=32),
            nullable=False,
            server_default="filesystem",
        ),
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
            "tenant_id", "object_key", name="uq_product_images_tenant_key"
        ),
    )
    op.create_index(
        "ix_product_images_tenant_product",
        "product_images",
        ["tenant_id", "product_id"],
    )
    op.create_index(
        "ix_product_images_tenant_variant",
        "product_images",
        ["tenant_id", "variant_id"],
    )
    if is_pg:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_product_images_primary_product "
                "ON product_images (tenant_id, product_id) "
                "WHERE archived_at IS NULL AND is_primary IS TRUE AND variant_id IS NULL"
            )
        )
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_product_images_primary_variant "
                "ON product_images (tenant_id, variant_id) "
                "WHERE archived_at IS NULL AND is_primary IS TRUE "
                "AND variant_id IS NOT NULL"
            )
        )
    else:
        op.create_index(
            "uq_product_images_primary_product",
            "product_images",
            ["tenant_id", "product_id"],
            unique=True,
            sqlite_where=sa.text(
                "archived_at IS NULL AND is_primary = 1 AND variant_id IS NULL"
            ),
        )
        op.create_index(
            "uq_product_images_primary_variant",
            "product_images",
            ["tenant_id", "variant_id"],
            unique=True,
            sqlite_where=sa.text(
                "archived_at IS NULL AND is_primary = 1 AND variant_id IS NOT NULL"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.execute(sa.text("DROP INDEX IF EXISTS uq_product_images_primary_variant"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_product_images_primary_product"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_product_variants_fingerprint"))
    else:
        op.drop_index("uq_product_images_primary_variant", table_name="product_images")
        op.drop_index("uq_product_images_primary_product", table_name="product_images")
        op.drop_index("uq_product_variants_fingerprint", table_name="product_variants")

    op.drop_table("product_images")
    op.drop_table("product_variant_attribute_values")
    op.drop_table("product_variants")
    op.drop_table("product_attribute_values")
    op.drop_table("product_attributes")
    op.drop_table("products")
    op.drop_table("catalog_skus")
    op.drop_table("product_categories")
    op.drop_table("product_brands")

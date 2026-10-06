"""Phase 6 Inventory domain."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0032_inventory"
down_revision = "0031_product_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.create_table(
        "inventory_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("code_normalized", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "location_type",
            sa.String(length=32),
            nullable=False,
            server_default="OTHER",
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("address_metadata", sa.JSON(), nullable=False, server_default="{}"),
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
            "tenant_id", "code_normalized", name="uq_inventory_locations_code"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="ck_inventory_locations_status",
        ),
        sa.CheckConstraint(
            "location_type IN ('WAREHOUSE', 'STORE', 'OFFICE', 'VEHICLE', 'FIELD', 'OTHER')",
            name="ck_inventory_locations_type",
        ),
    )
    op.create_index(
        "ix_inventory_locations_tenant_status",
        "inventory_locations",
        ["tenant_id", "status"],
    )

    op.create_table(
        "inventory_items",
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
            "sku_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("catalog_skus.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tracking_mode",
            sa.String(length=32),
            nullable=False,
            server_default="VARIANT",
        ),
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
            "tracking_mode IN ('VARIANT')",
            name="ck_inventory_items_tracking_mode",
        ),
    )
    op.create_index(
        "ix_inventory_items_tenant_variant",
        "inventory_items",
        ["tenant_id", "variant_id"],
        unique=True,
    )

    op.create_table(
        "inventory_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minimum_stock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_alert_status", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
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
            "tenant_id",
            "inventory_item_id",
            "location_id",
            name="uq_inventory_balances_item_location",
        ),
        sa.CheckConstraint("stock_quantity >= 0", name="ck_inventory_balances_stock_nonneg"),
        sa.CheckConstraint(
            "reserved_quantity >= 0", name="ck_inventory_balances_reserved_nonneg"
        ),
        sa.CheckConstraint("minimum_stock >= 0", name="ck_inventory_balances_min_nonneg"),
        sa.CheckConstraint(
            "reserved_quantity <= stock_quantity",
            name="ck_inventory_balances_reserved_lte_stock",
        ),
    )
    op.create_index(
        "ix_inventory_balances_tenant_location",
        "inventory_balances",
        ["tenant_id", "location_id"],
    )

    op.create_table(
        "inventory_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("stock_before", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("reserved_before", sa.Integer(), nullable=False),
        sa.Column("reserved_after", sa.Integer(), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("quantity <> 0", name="ck_inventory_transactions_quantity_nonzero"),
        sa.CheckConstraint(
            "transaction_type IN ('PURCHASE', 'SALE', 'ADJUSTMENT', 'RETURN', "
            "'RESERVATION', 'RELEASE')",
            name="ck_inventory_transactions_type",
        ),
    )
    op.create_index(
        "ix_inventory_transactions_item_loc_created",
        "inventory_transactions",
        ["tenant_id", "inventory_item_id", "location_id", "created_at"],
    )
    op.create_index(
        "ix_inventory_transactions_type_created",
        "inventory_transactions",
        ["tenant_id", "transaction_type", "created_at"],
    )
    if is_pg:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_inventory_transactions_idempotency "
                "ON inventory_transactions (tenant_id, idempotency_key) "
                "WHERE idempotency_key IS NOT NULL"
            )
        )
    else:
        op.create_index(
            "uq_inventory_transactions_idempotency",
            "inventory_transactions",
            ["tenant_id", "idempotency_key"],
            unique=True,
        )

    op.create_table(
        "inventory_alert_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default="false"),
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
            "tenant_id",
            "inventory_item_id",
            "location_id",
            name="uq_inventory_alert_config_item_location",
        ),
    )

    op.create_table(
        "inventory_alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "inventory_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inventory_locations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("minimum_stock", sa.Integer(), nullable=False),
        sa.Column(
            "email_notification_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "sms_notification_status",
            sa.String(length=32),
            nullable=False,
            server_default="skipped",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "alert_type IN ('LOW_STOCK', 'OUT_OF_STOCK', 'RECOVERED')",
            name="ck_inventory_alert_events_type",
        ),
    )
    op.create_index(
        "ix_inventory_alert_events_item_loc_created",
        "inventory_alert_events",
        ["tenant_id", "inventory_item_id", "location_id", "created_at"],
    )

    op.create_table(
        "inventory_outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_inventory_outbox_idempotency",
        ),
    )
    op.create_index(
        "ix_inventory_outbox_tenant_status_created",
        "inventory_outbox_events",
        ["tenant_id", "status", "created_at"],
    )

    op.create_foreign_key(
        "fk_product_variants_inventory_item",
        "product_variants",
        "inventory_items",
        ["inventory_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _backfill_stock_on_hand(bind)

    from sqlalchemy.orm import Session

    from callbot_platform.rbac.reconcile import reconcile_all_tenants

    session = Session(bind=bind)
    try:
        reconcile_all_tenants(session, actor="migration:0032", freeze_existing_gaps=False)
        session.commit()
    finally:
        session.close()


def _backfill_stock_on_hand(bind) -> None:
    """Migrate transitional product_variants.stock_on_hand into inventory balances."""
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    session = Session(bind=bind)
    try:
        rows = session.execute(
            text(
                "SELECT id, tenant_id, stock_on_hand FROM product_variants "
                "WHERE stock_on_hand IS NOT NULL AND stock_on_hand > 0 "
                "AND inventory_item_id IS NULL"
            )
        ).all()
        default_locations: dict[uuid.UUID, uuid.UUID] = {}
        for variant_id, tenant_id, stock in rows:
            tid = uuid.UUID(str(tenant_id))
            vid = uuid.UUID(str(variant_id))
            stock_int = int(stock)
            if tid not in default_locations:
                loc_id = uuid.uuid4()
                session.execute(
                    text(
                        "INSERT INTO inventory_locations "
                        "(id, tenant_id, name, code, code_normalized, location_type, "
                        "status, is_default, address_metadata, created_at, updated_at) "
                        "VALUES (:id, :tenant_id, 'Primary', 'PRIMARY', 'PRIMARY', "
                        "'OTHER', 'ACTIVE', true, '{}', :now, :now)"
                    ),
                    {"id": loc_id, "tenant_id": tid, "now": datetime.now(UTC)},
                )
                default_locations[tid] = loc_id
            loc_id = default_locations[tid]
            item_id = uuid.uuid4()
            session.execute(
                text(
                    "INSERT INTO inventory_items "
                    "(id, tenant_id, variant_id, tracking_mode, created_at, updated_at) "
                    "VALUES (:id, :tenant_id, :variant_id, 'VARIANT', :now, :now)"
                ),
                {
                    "id": item_id,
                    "tenant_id": tid,
                    "variant_id": vid,
                    "now": datetime.now(UTC),
                },
            )
            session.execute(
                text(
                    "UPDATE product_variants SET inventory_item_id = :item_id "
                    "WHERE id = :variant_id AND tenant_id = :tenant_id"
                ),
                {"item_id": item_id, "variant_id": vid, "tenant_id": tid},
            )
            balance_id = uuid.uuid4()
            session.execute(
                text(
                    "INSERT INTO inventory_balances "
                    "(id, tenant_id, inventory_item_id, location_id, stock_quantity, "
                    "reserved_quantity, minimum_stock, version, created_at, updated_at) "
                    "VALUES (:id, :tenant_id, :item_id, :loc_id, :stock, 0, 0, 0, :now, :now)"
                ),
                {
                    "id": balance_id,
                    "tenant_id": tid,
                    "item_id": item_id,
                    "loc_id": loc_id,
                    "stock": stock_int,
                    "now": datetime.now(UTC),
                },
            )
            tx_id = uuid.uuid4()
            session.execute(
                text(
                    "INSERT INTO inventory_transactions "
                    "(id, tenant_id, inventory_item_id, location_id, transaction_type, "
                    "quantity, stock_before, stock_after, reserved_before, reserved_after, "
                    "reason, metadata, created_by, created_at, idempotency_key) "
                    "VALUES (:id, :tenant_id, :item_id, :loc_id, 'ADJUSTMENT', :qty, "
                    "0, :qty, 0, 0, 'migration:0032_stock_on_hand', '{}', "
                    "'migration:0032', :now, :idem)"
                ),
                {
                    "id": tx_id,
                    "tenant_id": tid,
                    "item_id": item_id,
                    "loc_id": loc_id,
                    "qty": stock_int,
                    "now": datetime.now(UTC),
                    "idem": f"migration:0032:{vid}",
                },
            )
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    op.drop_constraint(
        "fk_product_variants_inventory_item", "product_variants", type_="foreignkey"
    )
    op.drop_table("inventory_outbox_events")
    op.drop_table("inventory_alert_events")
    op.drop_table("inventory_alert_configurations")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS uq_inventory_transactions_idempotency"))
    else:
        op.drop_index(
            "uq_inventory_transactions_idempotency", table_name="inventory_transactions"
        )
    op.drop_table("inventory_transactions")
    op.drop_table("inventory_balances")
    op.drop_table("inventory_items")
    op.drop_table("inventory_locations")

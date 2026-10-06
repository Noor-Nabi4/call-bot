"""Phase 4 Customer CRM: extend customers, locations, tags, notes, search indexes.

Implementation-gate override: local schema only. Staging/production readiness remains
blocked (see docs/PRODUCTION_READINESS.md and docs/CUSTOMER_CRM.md).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030_customer_crm"
down_revision = "0029_dynamic_crm_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    op.add_column("customers", sa.Column("first_name", sa.String(length=128), nullable=True))
    op.add_column("customers", sa.Column("last_name", sa.String(length=128), nullable=True))
    op.add_column(
        "customers", sa.Column("email_normalized", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "customers",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column("customers", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "customers",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customers", sa.Column("created_by", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "customers", sa.Column("updated_by", sa.String(length=255), nullable=True)
    )

    # Deterministic backfill: normalize existing emails for search.
    op.execute(
        sa.text(
            """
            UPDATE customers
            SET email_normalized = lower(trim(email))
            WHERE email IS NOT NULL AND trim(email) <> ''
            """
        )
    )

    op.create_check_constraint(
        "ck_customers_status",
        "customers",
        "status IN ('ACTIVE', 'INACTIVE')",
    )
    op.create_index(
        "ix_customers_tenant_email_normalized",
        "customers",
        ["tenant_id", "email_normalized"],
    )
    op.create_index(
        "ix_customers_tenant_status", "customers", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_customers_tenant_archived", "customers", ["tenant_id", "archived_at"]
    )
    op.create_index(
        "ix_customers_tenant_created", "customers", ["tenant_id", "created_at"]
    )
    op.create_index("ix_customers_tenant_name", "customers", ["tenant_id", "name"])

    if is_pg:
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_customers_tenant_name_trgm "
                "ON customers USING gin (tenant_id, name gin_trgm_ops)"
            )
        )
        # gin on (tenant_id, name) may not work that way — use expression on name only
        # with tenant filter in queries. Prefer tenant_id btree + name trgm:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_customers_tenant_name_trgm"))
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_customers_name_trgm "
                "ON customers USING gin (name gin_trgm_ops)"
            )
        )

    op.create_index(
        "ix_customer_phones_tenant_e164",
        "customer_phones",
        ["tenant_id", "e164"],
    )

    op.create_table(
        "customer_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("address_line_1", sa.String(length=255), nullable=False),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("access_instructions", sa.Text(), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_customer_locations_latitude",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_customer_locations_longitude",
        ),
    )
    op.create_index(
        "ix_customer_locations_tenant_id", "customer_locations", ["tenant_id"]
    )
    op.create_index(
        "ix_customer_locations_tenant_customer",
        "customer_locations",
        ["tenant_id", "customer_id"],
    )
    op.create_index(
        "ix_customer_locations_tenant_postal",
        "customer_locations",
        ["tenant_id", "postal_code"],
    )
    op.create_index(
        "ix_customer_locations_tenant_city",
        "customer_locations",
        ["tenant_id", "city"],
    )
    if is_pg:
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_customer_locations_one_primary "
                "ON customer_locations (tenant_id, customer_id) "
                "WHERE archived_at IS NULL AND is_primary IS TRUE"
            )
        )
        op.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_customer_locations_address_trgm "
                "ON customer_locations USING gin (address_line_1 gin_trgm_ops)"
            )
        )
    else:
        op.create_index(
            "uq_customer_locations_one_primary",
            "customer_locations",
            ["tenant_id", "customer_id"],
            unique=True,
            sqlite_where=sa.text("archived_at IS NULL AND is_primary = 1"),
        )

    op.create_table(
        "customer_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("name_normalized", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "name_normalized", name="uq_customer_tags_tenant_name"
        ),
    )
    op.create_index("ix_customer_tags_tenant_id", "customer_tags", ["tenant_id"])

    op.create_table(
        "customer_tag_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_tags.id", ondelete="CASCADE"),
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
            "customer_id",
            "tag_id",
            name="uq_customer_tag_links_assignment",
        ),
    )
    op.create_index(
        "ix_customer_tag_links_tenant_customer",
        "customer_tag_links",
        ["tenant_id", "customer_id"],
    )
    op.create_index(
        "ix_customer_tag_links_tenant_tag",
        "customer_tag_links",
        ["tenant_id", "tag_id"],
    )

    op.create_table(
        "customer_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_customer_notes_tenant_id", "customer_notes", ["tenant_id"])
    op.create_index(
        "ix_customer_notes_tenant_customer",
        "customer_notes",
        ["tenant_id", "customer_id"],
    )
    op.create_index(
        "ix_customer_notes_tenant_created",
        "customer_notes",
        ["tenant_id", "created_at"],
    )

    # Drop server defaults that were only for backfill safety.
    op.alter_column("customers", "status", server_default=None)
    op.alter_column("customer_locations", "is_primary", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.drop_table("customer_notes")
    op.drop_table("customer_tag_links")
    op.drop_table("customer_tags")

    if is_pg:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_customer_locations_address_trgm"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_customer_locations_one_primary"))
    else:
        op.drop_index(
            "uq_customer_locations_one_primary", table_name="customer_locations"
        )
    op.drop_table("customer_locations")

    op.drop_index("ix_customer_phones_tenant_e164", table_name="customer_phones")
    if is_pg:
        op.execute(sa.text("DROP INDEX IF EXISTS ix_customers_name_trgm"))
    op.drop_index("ix_customers_tenant_name", table_name="customers")
    op.drop_index("ix_customers_tenant_created", table_name="customers")
    op.drop_index("ix_customers_tenant_archived", table_name="customers")
    op.drop_index("ix_customers_tenant_status", table_name="customers")
    op.drop_index("ix_customers_tenant_email_normalized", table_name="customers")
    op.drop_constraint("ck_customers_status", "customers", type_="check")
    op.drop_column("customers", "updated_by")
    op.drop_column("customers", "created_by")
    op.drop_column("customers", "archived_at")
    op.drop_column("customers", "notes")
    op.drop_column("customers", "status")
    op.drop_column("customers", "email_normalized")
    op.drop_column("customers", "last_name")
    op.drop_column("customers", "first_name")

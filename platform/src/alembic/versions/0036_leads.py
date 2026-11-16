"""Phase 8 Leads domain: extend existing leads + notes/activities/conversions."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0036_leads"
down_revision = "0035_services_pricebook_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # --- Extend leads ---
    with op.batch_alter_table("leads") as batch:
        batch.add_column(
            sa.Column("title", sa.String(length=255), nullable=True)
        )
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "source",
                sa.String(length=32),
                nullable=False,
                server_default="OTHER",
            )
        )
        batch.add_column(
            sa.Column(
                "priority",
                sa.String(length=32),
                nullable=False,
                server_default="MEDIUM",
            )
        )
        batch.add_column(
            sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch.add_column(
            sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch.add_column(
            sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch.add_column(
            sa.Column("prospect_name", sa.String(length=255), nullable=True)
        )
        batch.add_column(
            sa.Column("prospect_phone", sa.String(length=32), nullable=True)
        )
        batch.add_column(
            sa.Column("prospect_email", sa.String(length=255), nullable=True)
        )
        batch.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("created_by", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("updated_by", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("converted_by", sa.String(length=255), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "converted_customer_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,
            )
        )

    # Backfill title / normalize status / map urgency → priority / source
    op.execute(
        sa.text(
            """
            UPDATE leads
            SET title = CASE
                    WHEN title IS NULL OR title = '' THEN service_type
                    ELSE title
                END,
                status = CASE lower(status)
                    WHEN 'new' THEN 'NEW'
                    WHEN 'qualified' THEN 'QUALIFIED'
                    WHEN 'contacted' THEN 'CONTACTED'
                    WHEN 'booked' THEN 'BOOKED'
                    WHEN 'won' THEN 'WON'
                    WHEN 'lost' THEN 'LOST'
                    ELSE upper(status)
                END,
                priority = CASE lower(urgency)
                    WHEN 'low' THEN 'LOW'
                    WHEN 'high' THEN 'HIGH'
                    WHEN 'urgent' THEN 'URGENT'
                    ELSE 'MEDIUM'
                END,
                source = CASE
                    WHEN call_id IS NOT NULL THEN 'AI_AGENT'
                    ELSE source
                END
            """
        )
    )

    with op.batch_alter_table("leads") as batch:
        batch.alter_column(
            "title",
            existing_type=sa.String(length=255),
            nullable=False,
            server_default="",
        )
        batch.alter_column(
            "customer_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
        )

    # Drop old cascade FK and recreate as SET NULL (batch-safe where possible)
    if is_pg:
        op.drop_constraint("leads_customer_id_fkey", "leads", type_="foreignkey")
        op.create_foreign_key(
            "leads_customer_id_fkey",
            "leads",
            "customers",
            ["customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_leads_service_id",
            "leads",
            "services",
            ["service_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_leads_product_id",
            "leads",
            "products",
            ["product_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_leads_owner_user_id",
            "leads",
            "tenant_users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_leads_converted_customer_id",
            "leads",
            "customers",
            ["converted_customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_check_constraint(
            "ck_leads_status",
            "leads",
            "status IN ('NEW', 'QUALIFIED', 'CONTACTED', 'BOOKED', 'WON', 'LOST')",
        )
        op.create_check_constraint(
            "ck_leads_priority",
            "leads",
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
        )
        op.create_check_constraint(
            "ck_leads_source",
            "leads",
            "source IN ('PHONE', 'WEBSITE', 'REFERRAL', 'SOCIAL', 'EMAIL', "
            "'AD', 'WALK_IN', 'AI_AGENT', 'OTHER')",
        )
    else:
        # SQLite: recreate via batch for FKs/checks where supported
        with op.batch_alter_table("leads") as batch:
            batch.create_foreign_key(
                "fk_leads_service_id",
                "services",
                ["service_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_foreign_key(
                "fk_leads_product_id",
                "products",
                ["product_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_foreign_key(
                "fk_leads_owner_user_id",
                "tenant_users",
                ["owner_user_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch.create_foreign_key(
                "fk_leads_converted_customer_id",
                "customers",
                ["converted_customer_id"],
                ["id"],
                ondelete="SET NULL",
            )

    op.create_index("ix_leads_tenant_status", "leads", ["tenant_id", "status"])
    op.create_index("ix_leads_tenant_owner", "leads", ["tenant_id", "owner_user_id"])
    op.create_index("ix_leads_tenant_source", "leads", ["tenant_id", "source"])
    op.create_index("ix_leads_tenant_priority", "leads", ["tenant_id", "priority"])
    op.create_index("ix_leads_tenant_service", "leads", ["tenant_id", "service_id"])
    op.create_index("ix_leads_tenant_product", "leads", ["tenant_id", "product_id"])
    op.create_index("ix_leads_tenant_archived", "leads", ["tenant_id", "archived_at"])
    op.create_index("ix_leads_tenant_updated", "leads", ["tenant_id", "updated_at"])
    op.create_index("ix_leads_tenant_created", "leads", ["tenant_id", "created_at"])

    # --- lead_notes ---
    op.create_table(
        "lead_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
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
    )
    op.create_index("ix_lead_notes_tenant_id", "lead_notes", ["tenant_id"])
    op.create_index(
        "ix_lead_notes_tenant_lead", "lead_notes", ["tenant_id", "lead_id"]
    )
    op.create_index(
        "ix_lead_notes_tenant_created", "lead_notes", ["tenant_id", "created_at"]
    )

    # --- lead_activities ---
    op.create_table(
        "lead_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor", sa.String(length=255), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_lead_activities_tenant_id", "lead_activities", ["tenant_id"])
    op.create_index(
        "ix_lead_activities_tenant_lead",
        "lead_activities",
        ["tenant_id", "lead_id"],
    )
    op.create_index(
        "ix_lead_activities_tenant_created",
        "lead_activities",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_lead_activities_tenant_type",
        "lead_activities",
        ["tenant_id", "activity_type"],
    )
    if is_pg:
        op.create_check_constraint(
            "ck_lead_activities_type",
            "lead_activities",
            "activity_type IN ("
            "'CREATED', 'STATUS_CHANGED', 'NOTE_ADDED', 'NOTE_UPDATED', "
            "'NOTE_DELETED', 'OWNER_CHANGED', 'CUSTOMER_LINKED', "
            "'SERVICE_LINKED', 'PRODUCT_LINKED', 'CONTACTED', 'BOOKED', "
            "'WON', 'LOST', 'CONVERTED', 'UPDATED', 'ARCHIVED', 'RESTORED'"
            ")",
        )

    # --- lead_conversions ---
    op.create_table(
        "lead_conversions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_customer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("converted_by", sa.String(length=255), nullable=True),
        sa.Column(
            "converted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "lead_id", name="uq_lead_conversions_tenant_lead"
        ),
    )
    op.create_index("ix_lead_conversions_tenant_id", "lead_conversions", ["tenant_id"])
    op.create_index(
        "ix_lead_conversions_tenant_customer",
        "lead_conversions",
        ["tenant_id", "customer_id"],
    )


def downgrade() -> None:
    op.drop_table("lead_conversions")
    op.drop_table("lead_activities")
    op.drop_table("lead_notes")

    op.drop_index("ix_leads_tenant_created", table_name="leads")
    op.drop_index("ix_leads_tenant_updated", table_name="leads")
    op.drop_index("ix_leads_tenant_archived", table_name="leads")
    op.drop_index("ix_leads_tenant_product", table_name="leads")
    op.drop_index("ix_leads_tenant_service", table_name="leads")
    op.drop_index("ix_leads_tenant_priority", table_name="leads")
    op.drop_index("ix_leads_tenant_source", table_name="leads")
    op.drop_index("ix_leads_tenant_owner", table_name="leads")
    op.drop_index("ix_leads_tenant_status", table_name="leads")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_leads_source", "leads", type_="check")
        op.drop_constraint("ck_leads_priority", "leads", type_="check")
        op.drop_constraint("ck_leads_status", "leads", type_="check")
        op.drop_constraint("fk_leads_converted_customer_id", "leads", type_="foreignkey")
        op.drop_constraint("fk_leads_owner_user_id", "leads", type_="foreignkey")
        op.drop_constraint("fk_leads_product_id", "leads", type_="foreignkey")
        op.drop_constraint("fk_leads_service_id", "leads", type_="foreignkey")

    with op.batch_alter_table("leads") as batch:
        for col in (
            "converted_customer_id",
            "converted_by",
            "converted_at",
            "updated_by",
            "created_by",
            "archived_at",
            "prospect_email",
            "prospect_phone",
            "prospect_name",
            "owner_user_id",
            "product_id",
            "service_id",
            "priority",
            "source",
            "description",
            "title",
        ):
            batch.drop_column(col)

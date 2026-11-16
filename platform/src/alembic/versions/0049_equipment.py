"""Phase 21 Equipment/Assets: equipment, attachments, jobs.equipment_id."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0049_equipment"
down_revision = "0048_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment",
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
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("customer_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("manufacturer", sa.String(255), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("serial_number", sa.String(128), nullable=True),
        sa.Column("serial_number_normalized", sa.String(128), nullable=True),
        sa.Column("installation_date", sa.Date(), nullable=True),
        sa.Column("warranty_start_date", sa.Date(), nullable=True),
        sa.Column("warranty_end_date", sa.Date(), nullable=True),
        sa.Column("warranty_provider", sa.String(255), nullable=True),
        sa.Column("warranty_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE','RETIRED','REMOVED')",
            name="ck_equipment_status",
        ),
        sa.CheckConstraint(
            "warranty_end_date IS NULL OR warranty_start_date IS NULL OR "
            "warranty_end_date >= warranty_start_date",
            name="ck_equipment_warranty_dates",
        ),
    )
    op.create_index("ix_equipment_tenant_status", "equipment", ["tenant_id", "status"])
    op.create_index(
        "ix_equipment_tenant_customer", "equipment", ["tenant_id", "customer_id"]
    )
    op.create_index(
        "ix_equipment_tenant_location", "equipment", ["tenant_id", "location_id"]
    )
    op.create_index(
        "ix_equipment_tenant_manufacturer",
        "equipment",
        ["tenant_id", "manufacturer"],
    )
    op.create_index(
        "ix_equipment_tenant_model", "equipment", ["tenant_id", "model"]
    )
    op.create_index(
        "ix_equipment_tenant_install",
        "equipment",
        ["tenant_id", "installation_date"],
    )
    op.create_index(
        "ix_equipment_tenant_warranty_end",
        "equipment",
        ["tenant_id", "warranty_end_date"],
    )
    op.create_index(
        "ix_equipment_tenant_created", "equipment", ["tenant_id", "created_at"]
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_equipment_tenant_serial_norm
        ON equipment (tenant_id, serial_number_normalized)
        WHERE serial_number_normalized IS NOT NULL
        """
    )

    op.create_table(
        "equipment_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "equipment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="PHOTO"),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "object_key",
            name="uq_equipment_attachments_tenant_object_key",
        ),
        sa.CheckConstraint(
            "kind IN ('PHOTO','INSTALLATION','REPAIR','BEFORE','AFTER','OTHER')",
            name="ck_equipment_attachments_kind",
        ),
        sa.CheckConstraint(
            "size_bytes >= 0", name="ck_equipment_attachments_size_nonneg"
        ),
    )
    op.create_index(
        "ix_equipment_attachments_tenant_equipment",
        "equipment_attachments",
        ["tenant_id", "equipment_id"],
    )

    op.add_column(
        "jobs",
        sa.Column(
            "equipment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equipment.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_jobs_tenant_equipment", "jobs", ["tenant_id", "equipment_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_tenant_equipment", table_name="jobs")
    op.drop_column("jobs", "equipment_id")
    op.drop_table("equipment_attachments")
    op.execute("DROP INDEX IF EXISTS uq_equipment_tenant_serial_norm")
    op.drop_table("equipment")

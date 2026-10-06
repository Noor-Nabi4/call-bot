"""Extend CRM config for Dynamic CRM Engine (modules, fields, objects, relationships)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0028_dynamic_crm_engine"
down_revision = "0027_business_crm_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organization_crm_modules",
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
    )

    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "owner_scope",
            sa.String(length=16),
            nullable=False,
            server_default="module",
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "owner_key",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "description",
            sa.String(length=512),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "field_type",
            sa.String(length=32),
            nullable=False,
            server_default="TEXT",
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="100",
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "default_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "validation_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "organization_crm_fields",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Backfill owner_key from module_key for existing Phase 2 rows.
    op.execute(
        sa.text(
            "UPDATE organization_crm_fields "
            "SET owner_scope = 'module', owner_key = COALESCE(module_key, '') "
            "WHERE owner_key = '' OR owner_key IS NULL"
        )
    )

    op.drop_constraint(
        "uq_organization_crm_fields_tenant_module_field",
        "organization_crm_fields",
        type_="unique",
    )
    op.alter_column(
        "organization_crm_fields",
        "module_key",
        existing_type=sa.String(length=64),
        nullable=True,
    )
    op.create_unique_constraint(
        "uq_organization_crm_fields_tenant_owner_field",
        "organization_crm_fields",
        ["tenant_id", "owner_scope", "owner_key", "field_key"],
    )
    op.create_index(
        "ix_organization_crm_fields_tenant_owner",
        "organization_crm_fields",
        ["tenant_id", "owner_scope", "owner_key"],
    )

    op.create_table(
        "organization_custom_object_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("plural_name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("icon", sa.String(length=64), nullable=False, server_default="box"),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "source", sa.String(length=32), nullable=False, server_default="ORG_CUSTOM"
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "object_key",
            name="uq_org_custom_object_definitions_tenant_key",
        ),
    )
    op.create_index(
        "ix_org_custom_object_definitions_tenant_id",
        "organization_custom_object_definitions",
        ["tenant_id"],
    )

    op.create_table(
        "organization_custom_object_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "object_definition_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["object_definition_id"],
            ["organization_custom_object_definitions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_org_custom_object_records_tenant_id",
        "organization_custom_object_records",
        ["tenant_id"],
    )
    op.create_index(
        "ix_org_custom_object_records_tenant_object",
        "organization_custom_object_records",
        ["tenant_id", "object_definition_id"],
    )

    op.create_table(
        "crm_custom_field_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=16), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Numeric(24, 8), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["field_definition_id"],
            ["organization_crm_fields.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "field_definition_id",
            "record_id",
            name="uq_crm_custom_field_values_tenant_field_record",
        ),
    )
    op.create_index(
        "ix_crm_custom_field_values_tenant_id",
        "crm_custom_field_values",
        ["tenant_id"],
    )
    op.create_index(
        "ix_crm_custom_field_values_tenant_record",
        "crm_custom_field_values",
        ["tenant_id", "record_type", "record_id"],
    )
    op.create_index(
        "ix_crm_custom_field_values_tenant_field_text",
        "crm_custom_field_values",
        ["tenant_id", "field_definition_id", "value_text"],
    )
    op.create_index(
        "ix_crm_custom_field_values_tenant_field_number",
        "crm_custom_field_values",
        ["tenant_id", "field_definition_id", "value_number"],
    )

    op.create_table(
        "organization_crm_relationship_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_key", sa.String(length=64), nullable=False),
        sa.Column("relationship_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column(
            "inverse_label", sa.String(length=128), nullable=False, server_default=""
        ),
        sa.Column("cardinality", sa.String(length=32), nullable=False),
        sa.Column(
            "required", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "relationship_key",
            name="uq_org_crm_relationship_definitions_tenant_key",
        ),
    )
    op.create_index(
        "ix_org_crm_relationship_definitions_tenant_id",
        "organization_crm_relationship_definitions",
        ["tenant_id"],
    )

    op.create_table(
        "organization_crm_relationship_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["organization_crm_relationship_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "definition_id",
            "source_record_id",
            "target_record_id",
            name="uq_org_crm_relationship_links_edge",
        ),
    )
    op.create_index(
        "ix_org_crm_relationship_links_tenant_id",
        "organization_crm_relationship_links",
        ["tenant_id"],
    )
    op.create_index(
        "ix_org_crm_relationship_links_tenant_def_source",
        "organization_crm_relationship_links",
        ["tenant_id", "definition_id", "source_record_id"],
    )
    op.create_index(
        "ix_org_crm_relationship_links_tenant_def_target",
        "organization_crm_relationship_links",
        ["tenant_id", "definition_id", "target_record_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_org_crm_relationship_links_tenant_def_target",
        table_name="organization_crm_relationship_links",
    )
    op.drop_index(
        "ix_org_crm_relationship_links_tenant_def_source",
        table_name="organization_crm_relationship_links",
    )
    op.drop_index(
        "ix_org_crm_relationship_links_tenant_id",
        table_name="organization_crm_relationship_links",
    )
    op.drop_table("organization_crm_relationship_links")
    op.drop_index(
        "ix_org_crm_relationship_definitions_tenant_id",
        table_name="organization_crm_relationship_definitions",
    )
    op.drop_table("organization_crm_relationship_definitions")
    op.drop_index(
        "ix_crm_custom_field_values_tenant_field_number",
        table_name="crm_custom_field_values",
    )
    op.drop_index(
        "ix_crm_custom_field_values_tenant_field_text",
        table_name="crm_custom_field_values",
    )
    op.drop_index(
        "ix_crm_custom_field_values_tenant_record",
        table_name="crm_custom_field_values",
    )
    op.drop_index(
        "ix_crm_custom_field_values_tenant_id", table_name="crm_custom_field_values"
    )
    op.drop_table("crm_custom_field_values")
    op.drop_index(
        "ix_org_custom_object_records_tenant_object",
        table_name="organization_custom_object_records",
    )
    op.drop_index(
        "ix_org_custom_object_records_tenant_id",
        table_name="organization_custom_object_records",
    )
    op.drop_table("organization_custom_object_records")
    op.drop_index(
        "ix_org_custom_object_definitions_tenant_id",
        table_name="organization_custom_object_definitions",
    )
    op.drop_table("organization_custom_object_definitions")

    op.drop_index(
        "ix_organization_crm_fields_tenant_owner", table_name="organization_crm_fields"
    )
    op.drop_constraint(
        "uq_organization_crm_fields_tenant_owner_field",
        "organization_crm_fields",
        type_="unique",
    )
    op.execute(
        sa.text(
            "UPDATE organization_crm_fields "
            "SET module_key = owner_key "
            "WHERE module_key IS NULL AND owner_scope = 'module'"
        )
    )
    op.alter_column(
        "organization_crm_fields",
        "module_key",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_organization_crm_fields_tenant_module_field",
        "organization_crm_fields",
        ["tenant_id", "module_key", "field_key"],
    )
    op.drop_column("organization_crm_fields", "updated_at")
    op.drop_column("organization_crm_fields", "validation_rules")
    op.drop_column("organization_crm_fields", "configuration")
    op.drop_column("organization_crm_fields", "default_value")
    op.drop_column("organization_crm_fields", "display_order")
    op.drop_column("organization_crm_fields", "enabled")
    op.drop_column("organization_crm_fields", "required")
    op.drop_column("organization_crm_fields", "field_type")
    op.drop_column("organization_crm_fields", "description")
    op.drop_column("organization_crm_fields", "owner_key")
    op.drop_column("organization_crm_fields", "owner_scope")
    op.drop_column("organization_crm_modules", "display_order")

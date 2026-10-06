"""Add business_size and organization CRM configuration tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0027_business_crm_configuration"
down_revision = "0026_organization_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("business_size", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "organization_crm_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("industry_key", sa.String(length=64), nullable=True),
        sa.Column("business_model_key", sa.String(length=64), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "setup_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "settings_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
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
            "tenant_id", name="uq_organization_crm_configurations_tenant_id"
        ),
    )
    op.create_index(
        "ix_organization_crm_configurations_tenant_id",
        "organization_crm_configurations",
        ["tenant_id"],
    )

    op.create_table(
        "organization_crm_modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "source", sa.String(length=32), nullable=False, server_default="template"
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
        sa.UniqueConstraint(
            "tenant_id",
            "module_key",
            name="uq_organization_crm_modules_tenant_module",
        ),
    )
    op.create_index(
        "ix_organization_crm_modules_tenant_id",
        "organization_crm_modules",
        ["tenant_id"],
    )

    op.create_table(
        "organization_crm_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("status_key", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source", sa.String(length=32), nullable=False, server_default="template"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "module_key",
            "status_key",
            name="uq_organization_crm_statuses_tenant_module_status",
        ),
    )
    op.create_index(
        "ix_organization_crm_statuses_tenant_id",
        "organization_crm_statuses",
        ["tenant_id"],
    )

    op.create_table(
        "organization_crm_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False, server_default=""),
        sa.Column(
            "source", sa.String(length=32), nullable=False, server_default="template"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "module_key",
            "field_key",
            name="uq_organization_crm_fields_tenant_module_field",
        ),
    )
    op.create_index(
        "ix_organization_crm_fields_tenant_id",
        "organization_crm_fields",
        ["tenant_id"],
    )

    op.create_table(
        "organization_crm_workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workflow_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("module_key", sa.String(length=64), nullable=True),
        sa.Column(
            "stages_json",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "source", sa.String(length=32), nullable=False, server_default="template"
        ),
        sa.Column(
            "definition_json",
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
        sa.UniqueConstraint(
            "tenant_id",
            "workflow_key",
            name="uq_organization_crm_workflows_tenant_workflow",
        ),
    )
    op.create_index(
        "ix_organization_crm_workflows_tenant_id",
        "organization_crm_workflows",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_crm_workflows_tenant_id",
        table_name="organization_crm_workflows",
    )
    op.drop_table("organization_crm_workflows")
    op.drop_index(
        "ix_organization_crm_fields_tenant_id", table_name="organization_crm_fields"
    )
    op.drop_table("organization_crm_fields")
    op.drop_index(
        "ix_organization_crm_statuses_tenant_id",
        table_name="organization_crm_statuses",
    )
    op.drop_table("organization_crm_statuses")
    op.drop_index(
        "ix_organization_crm_modules_tenant_id", table_name="organization_crm_modules"
    )
    op.drop_table("organization_crm_modules")
    op.drop_index(
        "ix_organization_crm_configurations_tenant_id",
        table_name="organization_crm_configurations",
    )
    op.drop_table("organization_crm_configurations")
    op.drop_column("tenants", "business_size")

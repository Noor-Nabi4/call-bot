"""Dynamic CRM hardening indexes (date/datetime filters)."""

from __future__ import annotations

from alembic import op

revision = "0029_dynamic_crm_hardening"
down_revision = "0028_dynamic_crm_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_crm_custom_field_values_tenant_field_date",
        "crm_custom_field_values",
        ["tenant_id", "field_definition_id", "value_date"],
    )
    op.create_index(
        "ix_crm_custom_field_values_tenant_field_datetime",
        "crm_custom_field_values",
        ["tenant_id", "field_definition_id", "value_datetime"],
    )
    op.create_index(
        "ix_crm_custom_field_values_tenant_field_boolean",
        "crm_custom_field_values",
        ["tenant_id", "field_definition_id", "value_boolean"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_crm_custom_field_values_tenant_field_boolean",
        table_name="crm_custom_field_values",
    )
    op.drop_index(
        "ix_crm_custom_field_values_tenant_field_datetime",
        table_name="crm_custom_field_values",
    )
    op.drop_index(
        "ix_crm_custom_field_values_tenant_field_date",
        table_name="crm_custom_field_values",
    )

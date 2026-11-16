"""Add tenant automation_rules table."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_automation_rules"
down_revision = "0011_usage_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "automation_rules",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_key", sa.String(length=64), nullable=False),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column(
            "config",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
            "tenant_id", "name", name="uq_automation_rules_tenant_name"
        ),
    )
    op.create_index("ix_automation_rules_tenant_id", "automation_rules", ["tenant_id"])
    op.create_index(
        "ix_automation_rules_tenant_trigger",
        "automation_rules",
        ["tenant_id", "trigger_key", "is_enabled"],
    )


def downgrade() -> None:
    op.drop_index("ix_automation_rules_tenant_trigger", table_name="automation_rules")
    op.drop_index("ix_automation_rules_tenant_id", table_name="automation_rules")
    op.drop_table("automation_rules")

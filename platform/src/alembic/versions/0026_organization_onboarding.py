"""Add organization_onboarding for Phase 2 wizard state."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0026_organization_onboarding"
down_revision = "0025_rbac_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_onboarding",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="NOT_STARTED"
        ),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column(
            "completed_steps",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "skipped_steps",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "state_data",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("tenant_id", name="uq_organization_onboarding_tenant_id"),
    )
    op.create_index(
        "ix_organization_onboarding_tenant_id",
        "organization_onboarding",
        ["tenant_id"],
    )
    op.create_index(
        "ix_organization_onboarding_tenant_status",
        "organization_onboarding",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_onboarding_tenant_status",
        table_name="organization_onboarding",
    )
    op.drop_index(
        "ix_organization_onboarding_tenant_id",
        table_name="organization_onboarding",
    )
    op.drop_table("organization_onboarding")

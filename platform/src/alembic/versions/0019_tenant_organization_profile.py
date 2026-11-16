"""Add organization profile fields to tenants."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0019_tenant_organization_profile"
down_revision = "0018_call_cogs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("business_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="USD",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("country", sa.String(length=2), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("state", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("website", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("phone", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.alter_column("tenants", "currency", server_default=None)
    op.alter_column("tenants", "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "updated_at")
    op.drop_column("tenants", "email")
    op.drop_column("tenants", "phone")
    op.drop_column("tenants", "website")
    op.drop_column("tenants", "state")
    op.drop_column("tenants", "country")
    op.drop_column("tenants", "currency")
    op.drop_column("tenants", "business_type")

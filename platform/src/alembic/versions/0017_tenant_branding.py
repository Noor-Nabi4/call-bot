"""Add tenant_branding for white-label settings."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0017_tenant_branding"
down_revision = "0016_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_branding",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("logo_url", sa.String(length=2048), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("accent_color", sa.String(length=7), nullable=True),
        sa.Column("support_email", sa.String(length=255), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_branding_tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("tenant_branding")

"""Retention / compliance settings per tenant."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0007_admin"
down_revision = "0006_handoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_retention_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recording_retention_days", sa.Integer(), nullable=False),
        sa.Column("transcript_retention_days", sa.Integer(), nullable=False),
        sa.Column("audit_retention_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_retention_settings_tenant"),
    )


def downgrade() -> None:
    op.drop_table("tenant_retention_settings")

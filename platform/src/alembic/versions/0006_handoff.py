"""Human handoff settings schema."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006_handoff"
down_revision = "0005_knowledge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_handoff_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("escalation_phone_e164", sa.String(32), nullable=True),
        sa.Column("sip_outbound_trunk_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_handoff_settings_tenant"),
    )


def downgrade() -> None:
    op.drop_table("tenant_handoff_settings")

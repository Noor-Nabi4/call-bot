"""Add call_flow JSON to agent_profiles."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0013_call_flow"
down_revision = "0012_automation_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_profiles",
        sa.Column(
            "call_flow",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_profiles", "call_flow")

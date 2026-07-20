"""Add call quality review fields."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0014_call_quality"
down_revision = "0013_call_flow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calls",
        sa.Column("disposition_code", sa.String(length=64), nullable=True),
    )
    op.add_column("calls", sa.Column("quality_score", sa.Integer(), nullable=True))
    op.add_column(
        "calls",
        sa.Column("quality_notes", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "calls",
        sa.Column("quality_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "calls",
        sa.Column("quality_reviewed_by", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("calls", "quality_reviewed_by")
    op.drop_column("calls", "quality_reviewed_at")
    op.drop_column("calls", "quality_notes")
    op.drop_column("calls", "quality_score")
    op.drop_column("calls", "disposition_code")

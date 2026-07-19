"""Extend tenant agent settings with typed agent profile fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_agent_profile"
down_revision = "0007_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_agent_settings",
        sa.Column("assistant_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("business_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("tone", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column(
            "supported_languages",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("response_style", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column(
            "service_areas",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("business_hours_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("booking_rules", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("pricing_disclosure_policy", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("handoff_rules_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column(
            "restricted_topics",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column("custom_instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenant_agent_settings",
        sa.Column(
            "profile_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_agent_settings", "profile_version")
    op.drop_column("tenant_agent_settings", "custom_instructions")
    op.drop_column("tenant_agent_settings", "restricted_topics")
    op.drop_column("tenant_agent_settings", "handoff_rules_text")
    op.drop_column("tenant_agent_settings", "pricing_disclosure_policy")
    op.drop_column("tenant_agent_settings", "booking_rules")
    op.drop_column("tenant_agent_settings", "business_hours_summary")
    op.drop_column("tenant_agent_settings", "service_areas")
    op.drop_column("tenant_agent_settings", "response_style")
    op.drop_column("tenant_agent_settings", "supported_languages")
    op.drop_column("tenant_agent_settings", "tone")
    op.drop_column("tenant_agent_settings", "business_description")
    op.drop_column("tenant_agent_settings", "assistant_name")

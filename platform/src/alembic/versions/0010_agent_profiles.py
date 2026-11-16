"""Multi agent profiles, phone assignment, knowledge scope."""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0010_agent_profiles"
down_revision = "0009_saas_billing"
branch_labels = None
depends_on = None

_DEFAULT_TOOLS = json.dumps(
    {
        "crm": True,
        "scheduling": True,
        "knowledge": True,
        "handoff": True,
        "sms": True,
    }
)
_DEFAULT_HOURS = json.dumps(
    {
        "mon": [["09:00", "17:00"]],
        "tue": [["09:00", "17:00"]],
        "wed": [["09:00", "17:00"]],
        "thu": [["09:00", "17:00"]],
        "fri": [["09:00", "17:00"]],
        "sat": [],
        "sun": [],
    }
)


def upgrade() -> None:
    op.create_table(
        "agent_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("industry_key", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("business_prompt_facts", sa.JSON(), nullable=False),
        sa.Column("voice", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=True),
        sa.Column("assistant_name", sa.String(length=128), nullable=True),
        sa.Column("business_description", sa.Text(), nullable=True),
        sa.Column("tone", sa.String(length=64), nullable=True),
        sa.Column("supported_languages", sa.JSON(), nullable=False),
        sa.Column("response_style", sa.String(length=64), nullable=True),
        sa.Column("service_areas", sa.JSON(), nullable=False),
        sa.Column("business_hours_summary", sa.Text(), nullable=True),
        sa.Column("business_hours", sa.JSON(), nullable=False),
        sa.Column("booking_rules", sa.Text(), nullable=True),
        sa.Column("pricing_disclosure_policy", sa.Text(), nullable=True),
        sa.Column("handoff_rules_text", sa.Text(), nullable=True),
        sa.Column("restricted_topics", sa.JSON(), nullable=False),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("enabled_tools", sa.JSON(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_agent_profiles_tenant_slug"),
    )
    op.create_index("ix_agent_profiles_tenant_id", "agent_profiles", ["tenant_id"])
    op.create_index(
        "ix_agent_profiles_tenant_default",
        "agent_profiles",
        ["tenant_id", "is_default"],
    )

    op.add_column(
        "tenants",
        sa.Column("industry_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "default_agent_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.add_column(
        "tenant_phone_numbers",
        sa.Column(
            "agent_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_tenant_phone_numbers_agent_profile_id",
        "tenant_phone_numbers",
        ["agent_profile_id"],
    )

    op.add_column(
        "knowledge_articles",
        sa.Column(
            "agent_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_knowledge_articles_agent_profile_id",
        "knowledge_articles",
        ["agent_profile_id"],
    )

    # Migrate legacy tenant_agent_settings → default agent_profiles
    conn = op.get_bind()
    rows = (
        conn.execute(
            sa.text(
                """
            SELECT s.id, s.tenant_id, s.business_prompt_facts, s.voice, s.language,
                   s.greeting, s.assistant_name, s.business_description, s.tone,
                   s.supported_languages, s.response_style, s.service_areas,
                   s.business_hours_summary, s.booking_rules,
                   s.pricing_disclosure_policy, s.handoff_rules_text,
                   s.restricted_topics, s.custom_instructions, s.profile_version,
                   s.created_at, s.updated_at
            FROM tenant_agent_settings s
            """
            )
        )
        .mappings()
        .all()
    )

    for row in rows:
        profile_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO agent_profiles (
                    id, tenant_id, name, slug, agent_type, industry_key, status,
                    is_default, business_prompt_facts, voice, language, greeting,
                    assistant_name, business_description, tone, supported_languages,
                    response_style, service_areas, business_hours_summary,
                    business_hours, booking_rules, pricing_disclosure_policy,
                    handoff_rules_text, restricted_topics, custom_instructions,
                    enabled_tools, profile_version, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :name, :slug, :agent_type, NULL, :status,
                    true, :business_prompt_facts, :voice, :language, :greeting,
                    :assistant_name, :business_description, :tone, :supported_languages,
                    :response_style, :service_areas, :business_hours_summary,
                    CAST(:business_hours AS json), :booking_rules, :pricing_disclosure_policy,
                    :handoff_rules_text, :restricted_topics, :custom_instructions,
                    CAST(:enabled_tools AS json), :profile_version, :created_at, :updated_at
                )
                """
            ),
            {
                "id": profile_id,
                "tenant_id": row["tenant_id"],
                "name": "Main Receptionist",
                "slug": "main-receptionist",
                "agent_type": "receptionist",
                "status": "active",
                "business_prompt_facts": json.dumps(row["business_prompt_facts"] or {}),
                "voice": row["voice"] or "marin",
                "language": row["language"] or "en",
                "greeting": row["greeting"],
                "assistant_name": row["assistant_name"],
                "business_description": row["business_description"],
                "tone": row["tone"],
                "supported_languages": json.dumps(row["supported_languages"] or []),
                "response_style": row["response_style"],
                "service_areas": json.dumps(row["service_areas"] or []),
                "business_hours_summary": row["business_hours_summary"],
                "business_hours": _DEFAULT_HOURS,
                "booking_rules": row["booking_rules"],
                "pricing_disclosure_policy": row["pricing_disclosure_policy"],
                "handoff_rules_text": row["handoff_rules_text"],
                "restricted_topics": json.dumps(row["restricted_topics"] or []),
                "custom_instructions": row["custom_instructions"],
                "enabled_tools": _DEFAULT_TOOLS,
                "profile_version": int(row["profile_version"] or 1),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        )
        conn.execute(
            sa.text(
                """
                UPDATE tenants
                SET default_agent_profile_id = :profile_id
                WHERE id = :tenant_id
                """
            ),
            {"profile_id": profile_id, "tenant_id": row["tenant_id"]},
        )

    op.create_foreign_key(
        "fk_tenants_default_agent_profile_id",
        "tenants",
        "agent_profiles",
        ["default_agent_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_tenants_default_agent_profile_id", "tenants", type_="foreignkey"
    )
    op.drop_index(
        "ix_knowledge_articles_agent_profile_id", table_name="knowledge_articles"
    )
    op.drop_column("knowledge_articles", "agent_profile_id")
    op.drop_index(
        "ix_tenant_phone_numbers_agent_profile_id", table_name="tenant_phone_numbers"
    )
    op.drop_column("tenant_phone_numbers", "agent_profile_id")
    op.drop_column("tenants", "default_agent_profile_id")
    op.drop_column("tenants", "industry_key")
    op.drop_index("ix_agent_profiles_tenant_default", table_name="agent_profiles")
    op.drop_index("ix_agent_profiles_tenant_id", table_name="agent_profiles")
    op.drop_table("agent_profiles")

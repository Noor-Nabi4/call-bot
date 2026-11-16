"""Global geo reference catalogs: countries, regions, currencies, timezones."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "0058_geo_reference_catalogs"
down_revision = "0057_onboarding_mandatory_backfill"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _tables()

    if "geo_currencies" not in existing:
        op.create_table(
            "geo_currencies",
            sa.Column("code", sa.String(length=3), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("code"),
        )

    if "geo_timezones" not in existing:
        op.create_table(
            "geo_timezones",
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("name"),
        )

    if "geo_countries" not in existing:
        op.create_table(
            "geo_countries",
            sa.Column("code", sa.String(length=2), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("default_currency_code", sa.String(length=3), nullable=True),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["default_currency_code"],
                ["geo_currencies.code"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("code"),
        )

    if "geo_regions" not in existing:
        op.create_table(
            "geo_regions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("country_code", sa.String(length=2), nullable=False),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["country_code"],
                ["geo_countries.code"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "country_code", "code", name="uq_geo_regions_country_code"
            ),
        )

    bind = op.get_bind()
    indexes = {idx["name"] for idx in inspect(bind).get_indexes("geo_regions")}
    if "ix_geo_regions_country_code" not in indexes:
        op.create_index(
            "ix_geo_regions_country_code",
            "geo_regions",
            ["country_code"],
            unique=False,
        )

    # Seed reference data (idempotent) on the migration connection.
    from sqlalchemy.orm import Session

    from callbot_platform.geo.seed import ensure_geo_catalog

    with Session(bind=bind) as session:
        ensure_geo_catalog(session)
        session.flush()


def downgrade() -> None:
    existing = _tables()
    if "geo_regions" in existing:
        indexes = {
            idx["name"] for idx in inspect(op.get_bind()).get_indexes("geo_regions")
        }
        if "ix_geo_regions_country_code" in indexes:
            op.drop_index("ix_geo_regions_country_code", table_name="geo_regions")
        op.drop_table("geo_regions")
    if "geo_countries" in existing:
        op.drop_table("geo_countries")
    if "geo_timezones" in existing:
        op.drop_table("geo_timezones")
    if "geo_currencies" in existing:
        op.drop_table("geo_currencies")

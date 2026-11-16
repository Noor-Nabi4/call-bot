"""Phase 7 hardening: PostgreSQL exclusion constraints for effective ranges.

Adds btree_gist-backed EXCLUDE constraints so concurrent writers cannot
persist overlapping ACTIVE (non-archived) pricebook items or overrides for
the same tenant + pricebook + service scope.

Range semantics: inclusive [effective_from, effective_until] (NULL = unbounded).
Adjacent ranges that do not share an instant (e.g. until=T1, from=T1+ε) are allowed.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035_services_pricebook_hardening"
down_revision = "0034_services_pricebook"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Alembic default version_num is VARCHAR(32); this revision id is longer.
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(128)"
            )
        )
    elif bind.dialect.name == "sqlite":
        # SQLite ignores length; no-op for type width.
        pass

    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))

    # Inclusive timestamptz ranges; NULL bounds → ±infinity.
    op.execute(
        sa.text(
            """
            ALTER TABLE pricebook_items
            ADD CONSTRAINT excl_pricebook_items_active_effective
            EXCLUDE USING gist (
                tenant_id WITH =,
                pricebook_id WITH =,
                service_id WITH =,
                tstzrange(
                    COALESCE(effective_from, '-infinity'::timestamptz),
                    COALESCE(effective_until, 'infinity'::timestamptz),
                    '[]'
                ) WITH &&
            )
            WHERE (archived_at IS NULL AND status = 'ACTIVE')
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE pricebook_overrides
            ADD CONSTRAINT excl_pricebook_overrides_active_effective
            EXCLUDE USING gist (
                tenant_id WITH =,
                pricebook_id WITH =,
                service_id WITH =,
                tstzrange(
                    COALESCE(effective_from, '-infinity'::timestamptz),
                    COALESCE(effective_until, 'infinity'::timestamptz),
                    '[]'
                ) WITH &&
            )
            WHERE (archived_at IS NULL AND status = 'ACTIVE')
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        sa.text(
            "ALTER TABLE pricebook_overrides "
            "DROP CONSTRAINT IF EXISTS excl_pricebook_overrides_active_effective"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE pricebook_items "
            "DROP CONSTRAINT IF EXISTS excl_pricebook_items_active_effective"
        )
    )

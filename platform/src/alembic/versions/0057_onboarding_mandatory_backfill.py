"""Backfill COMPLETED onboarding for existing organizations (mandatory gate).

New signups create NOT_STARTED rows at account creation. Tenants that already
existed without an onboarding row are treated as legacy completed orgs so the
mandatory gate does not lock them out.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0057_onboarding_mandatory_backfill"
down_revision = "0056_usage_ledger_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO organization_onboarding (
                id,
                tenant_id,
                status,
                current_step,
                completed_steps,
                skipped_steps,
                progress_percent,
                state_data,
                started_at,
                completed_at,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid(),
                t.id,
                'COMPLETED',
                'review',
                CAST('[]' AS jsonb),
                CAST('[]' AS jsonb),
                100,
                CAST('{}' AS jsonb),
                NOW(),
                NOW(),
                NOW(),
                NOW()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1
                FROM organization_onboarding o
                WHERE o.tenant_id = t.id
            )
            """
        )
    )


def downgrade() -> None:
    # Non-destructive: leave backfilled rows in place.
    pass

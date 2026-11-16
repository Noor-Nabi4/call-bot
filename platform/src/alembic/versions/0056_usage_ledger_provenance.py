"""Phase 32 hardening: usage provenance + billing status on ledger entries."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0056_usage_ledger_provenance"
down_revision = "0055_usage_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usage_ledger_entries",
        sa.Column(
            "usage_provenance",
            sa.String(32),
            nullable=False,
            server_default="ACTUAL_INTERNAL",
        ),
    )
    op.add_column(
        "usage_ledger_entries",
        sa.Column("billing_status", sa.String(32), nullable=True),
    )
    op.add_column(
        "usage_ledger_entries",
        sa.Column(
            "entry_kind",
            sa.String(32),
            nullable=False,
            server_default="usage",
        ),
    )
    op.create_check_constraint(
        "ck_usage_ledger_entries_usage_provenance",
        "usage_ledger_entries",
        "usage_provenance IN ("
        "'ACTUAL_PROVIDER','ACTUAL_INTERNAL','CONFIGURED_RATE',"
        "'ALLOCATED_COST','ESTIMATED','UNAVAILABLE'"
        ")",
    )
    op.create_check_constraint(
        "ck_usage_ledger_entries_billing_status",
        "usage_ledger_entries",
        "billing_status IS NULL OR billing_status IN ("
        "'UNBILLED','ESTIMATED','INVOICED','PAID','VOIDED','ADJUSTED'"
        ")",
    )
    op.create_check_constraint(
        "ck_usage_ledger_entries_entry_kind",
        "usage_ledger_entries",
        "entry_kind IN ('usage','adjustment')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_usage_ledger_entries_entry_kind", "usage_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_usage_ledger_entries_billing_status", "usage_ledger_entries", type_="check"
    )
    op.drop_constraint(
        "ck_usage_ledger_entries_usage_provenance",
        "usage_ledger_entries",
        type_="check",
    )
    op.drop_column("usage_ledger_entries", "entry_kind")
    op.drop_column("usage_ledger_entries", "billing_status")
    op.drop_column("usage_ledger_entries", "usage_provenance")

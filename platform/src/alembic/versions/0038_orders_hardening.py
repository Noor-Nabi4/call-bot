"""Phase 9.1 Orders hardening: idempotency request fingerprint."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0038_orders_hardening"
down_revision = "0037_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(
            sa.Column(
                "idempotency_request_hash",
                sa.String(length=64),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("idempotency_request_hash")

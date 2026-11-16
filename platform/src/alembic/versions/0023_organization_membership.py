"""Organization membership status on tenant_users.

Reuse tenant_users as the membership table (unique per org+email).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0023_organization_membership"
down_revision = "0022_phase3_async_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_users",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "UPDATE tenant_users SET status = 'disabled' WHERE is_active IS FALSE"
            )
        )
    else:
        op.execute(
            sa.text("UPDATE tenant_users SET status = 'disabled' WHERE is_active = 0")
        )
    op.create_index(
        "ix_tenant_users_tenant_status",
        "tenant_users",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_users_tenant_status", table_name="tenant_users")
    op.drop_column("tenant_users", "status")

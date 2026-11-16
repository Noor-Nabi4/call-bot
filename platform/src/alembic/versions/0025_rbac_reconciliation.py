"""RBAC reconciliation: source tracking + tombstones for intentional revocations.

Adds:
- role_permissions.source (SYSTEM_DEFAULT | ORG_CUSTOM)
- role_permission_tombstones (intentional removal of a system default)

Upgrade strategy:
1. Add schema.
2. Freeze existing gaps on system roles as tombstones (preserve customization).
3. Grant only newly introduced catalog defaults via reconcile.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0025_rbac_reconciliation"
down_revision = "0024_organization_rbac"
branch_labels = None
depends_on = None

SOURCE_SYSTEM = "SYSTEM_DEFAULT"


def upgrade() -> None:
    op.add_column(
        "role_permissions",
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default=SOURCE_SYSTEM,
        ),
    )
    op.create_index("ix_role_permissions_source", "role_permissions", ["source"])

    op.create_table(
        "role_permission_tombstones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization_roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("permissions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permission_tombstones_role_permission",
        ),
    )
    op.create_index(
        "ix_role_permission_tombstones_role_id",
        "role_permission_tombstones",
        ["role_id"],
    )

    bind = op.get_bind()
    from sqlalchemy.orm import Session

    from callbot_platform.rbac import models as _rbac_models
    from callbot_platform.rbac.reconcile import reconcile_all_tenants

    _ = _rbac_models
    session = Session(bind=bind)
    try:
        reconcile_all_tenants(
            session,
            actor="migration:0025",
            freeze_existing_gaps=True,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    op.drop_index(
        "ix_role_permission_tombstones_role_id",
        table_name="role_permission_tombstones",
    )
    op.drop_table("role_permission_tombstones")
    op.drop_index("ix_role_permissions_source", table_name="role_permissions")
    op.drop_column("role_permissions", "source")

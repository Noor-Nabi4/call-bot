"""Organization-managed RBAC tables + seed/backfill existing memberships.

Keeps tenant_users.role as a compatibility field; member_roles is authoritative
for permission resolution after this migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024_organization_rbac"
down_revision = "0023_organization_membership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "resource", "action", name="uq_permissions_resource_action"
        ),
    )
    op.create_index("ix_permissions_resource", "permissions", ["resource"])

    op.create_table(
        "organization_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_organization_roles_tenant_name"
        ),
    )
    op.create_index(
        "ix_organization_roles_tenant_id", "organization_roles", ["tenant_id"]
    )
    op.create_index(
        "ix_organization_roles_tenant_active",
        "organization_roles",
        ["tenant_id", "is_active"],
    )

    op.create_table(
        "role_permissions",
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
        sa.Column(
            "scope",
            sa.String(length=32),
            nullable=False,
            server_default="ALL_ORGANIZATION",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "role_id", "permission_id", name="uq_role_permissions_role_permission"
        ),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index(
        "ix_role_permissions_permission_id", "role_permissions", ["permission_id"]
    )

    op.create_table(
        "member_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenant_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization_roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_user_id", "role_id", name="uq_member_roles_user_role"
        ),
    )
    op.create_index(
        "ix_member_roles_tenant_user_id", "member_roles", ["tenant_user_id"]
    )
    op.create_index("ix_member_roles_role_id", "member_roles", ["role_id"])

    # Data backfill via ORM (works for Postgres and SQLite tests using create_all).
    # Production Alembic runs this upgrade; tests create tables via metadata then call seed.
    bind = op.get_bind()
    from sqlalchemy.orm import Session

    from callbot_platform.db.models.base import Base
    from callbot_platform.rbac import models as _rbac_models  # noqa: F401
    from callbot_platform.rbac.seed import backfill_all_tenants

    # Ensure metadata knows about new tables (already created by op).
    _ = Base
    session = Session(bind=bind)
    try:
        backfill_all_tenants(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    op.drop_table("member_roles")
    op.drop_table("role_permissions")
    op.drop_table("organization_roles")
    op.drop_table("permissions")

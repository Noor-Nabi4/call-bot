"""Tenant DB strategy columns + hot-path list indexes."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0020_tenancy_scaling"
down_revision = "0019_tenant_organization_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "db_strategy",
            sa.String(length=32),
            nullable=False,
            server_default="shared",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("db_dsn_key", sa.String(length=128), nullable=True),
    )
    op.alter_column("tenants", "db_strategy", server_default=None)

    op.create_index(
        "ix_calls_tenant_status_started",
        "calls",
        ["tenant_id", "status", "started_at"],
        unique=False,
    )
    op.create_index(
        "ix_leads_tenant_status_created",
        "leads",
        ["tenant_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_tenant_status",
        "appointments",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_notification_outbox_tenant_status_created",
        "notification_outbox",
        ["tenant_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_telephony_audit_tenant_created",
        "telephony_audit_events",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_tenant_created",
        "jobs",
        ["tenant_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_profiles_tenant_status",
        "agent_profiles",
        ["tenant_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_profiles_tenant_status", table_name="agent_profiles")
    op.drop_index("ix_jobs_tenant_created", table_name="jobs")
    op.drop_index(
        "ix_telephony_audit_tenant_created", table_name="telephony_audit_events"
    )
    op.drop_index(
        "ix_notification_outbox_tenant_status_created",
        table_name="notification_outbox",
    )
    op.drop_index("ix_appointments_tenant_status", table_name="appointments")
    op.drop_index("ix_leads_tenant_status_created", table_name="leads")
    op.drop_index("ix_calls_tenant_status_started", table_name="calls")
    op.drop_column("tenants", "db_dsn_key")
    op.drop_column("tenants", "db_strategy")

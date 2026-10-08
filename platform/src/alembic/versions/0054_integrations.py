"""Phase 28 Integrations: connections, credentials, mappings, sync runs, webhooks, OAuth state."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0054_integrations"
down_revision = "0053_communication_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DISCONNECTED"),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("external_account_id", sa.String(255), nullable=True),
        sa.Column(
            "sync_direction", sa.String(32), nullable=False, server_default="IMPORT"
        ),
        sa.Column("sync_cursor", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "category IN ('crm', 'calendar', 'commerce', 'accounting')",
            name="ck_integration_connections_category",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'DISCONNECTED','CONNECTING','CONNECTED','SYNCING','SYNCED',"
            "'ERROR','REAUTH_REQUIRED','DISABLED'"
            ")",
            name="ck_integration_connections_status",
        ),
        sa.CheckConstraint(
            "sync_direction IN ('IMPORT','EXPORT','BIDIRECTIONAL')",
            name="ck_integration_connections_sync_direction",
        ),
        sa.UniqueConstraint(
            "tenant_id", "provider", name="uq_integration_connections_tenant_provider"
        ),
    )
    op.create_index(
        "ix_integration_connections_tenant_status",
        "integration_connections",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_integration_connections_tenant_category",
        "integration_connections",
        ["tenant_id", "category"],
    )

    op.create_table(
        "integration_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_token_enc", sa.Text(), nullable=True),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(32), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra_enc", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            name="uq_integration_credentials_tenant_integration",
        ),
    )
    op.create_index(
        "ix_integration_credentials_tenant", "integration_credentials", ["tenant_id"]
    )

    op.create_table(
        "integration_external_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("internal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("external_version", sa.String(128), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "entity_type",
            "external_id",
            name="uq_integration_ext_map_external",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "entity_type",
            "internal_id",
            name="uq_integration_ext_map_internal",
        ),
    )
    op.create_index(
        "ix_integration_ext_map_tenant_entity",
        "integration_external_mappings",
        ["tenant_id", "entity_type", "internal_id"],
    )

    op.create_table(
        "integration_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "async_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("async_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("direction", sa.String(32), nullable=False, server_default="IMPORT"),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("records_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_integration_sync_runs_status",
        ),
        sa.CheckConstraint(
            "direction IN ('IMPORT','EXPORT','BIDIRECTIONAL')",
            name="ck_integration_sync_runs_direction",
        ),
    )
    op.create_index(
        "ix_integration_sync_runs_tenant_integration",
        "integration_sync_runs",
        ["tenant_id", "integration_id"],
    )
    op.create_index(
        "ix_integration_sync_runs_tenant_created",
        "integration_sync_runs",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "integration_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="RECEIVED"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "integration_id",
            "provider_event_id",
            name="uq_integration_webhook_provider_event",
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED','PROCESSING','PROCESSED','FAILED','DUPLICATE')",
            name="ck_integration_webhook_status",
        ),
    )
    op.create_index(
        "ix_integration_webhook_tenant_status",
        "integration_webhook_events",
        ["tenant_id", "status"],
    )

    op.create_table(
        "integration_oauth_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("state", sa.String(128), nullable=False),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("state", name="uq_integration_oauth_states_state"),
    )
    op.create_index(
        "ix_integration_oauth_states_expires",
        "integration_oauth_states",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_integration_oauth_states_expires", table_name="integration_oauth_states"
    )
    op.drop_table("integration_oauth_states")
    op.drop_index(
        "ix_integration_webhook_tenant_status",
        table_name="integration_webhook_events",
    )
    op.drop_table("integration_webhook_events")
    op.drop_index(
        "ix_integration_sync_runs_tenant_created", table_name="integration_sync_runs"
    )
    op.drop_index(
        "ix_integration_sync_runs_tenant_integration",
        table_name="integration_sync_runs",
    )
    op.drop_table("integration_sync_runs")
    op.drop_index(
        "ix_integration_ext_map_tenant_entity",
        table_name="integration_external_mappings",
    )
    op.drop_table("integration_external_mappings")
    op.drop_index(
        "ix_integration_credentials_tenant", table_name="integration_credentials"
    )
    op.drop_table("integration_credentials")
    op.drop_index(
        "ix_integration_connections_tenant_category",
        table_name="integration_connections",
    )
    op.drop_index(
        "ix_integration_connections_tenant_status",
        table_name="integration_connections",
    )
    op.drop_table("integration_connections")

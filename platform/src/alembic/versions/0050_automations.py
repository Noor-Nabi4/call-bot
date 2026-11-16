"""Phase 22 Automation Engine: events, workflows, executions, tasks, reminders."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0050_automations"
down_revision = "0049_equipment"
branch_labels = None
depends_on = None

_EVENT_TYPES = (
    "CALL_COMPLETED",
    "LEAD_CREATED",
    "JOB_CREATED",
    "APPOINTMENT_CREATED",
    "APPOINTMENT_REMINDER",
    "TECHNICIAN_DISPATCHED",
    "JOB_COMPLETED",
    "ESTIMATE_SENT",
    "ESTIMATE_APPROVED",
    "INVOICE_CREATED",
    "PAYMENT_COMPLETED",
    "ORDER_CREATED",
    "ORDER_SHIPPED",
)


def upgrade() -> None:
    event_enum = ", ".join(f"'{e}'" for e in _EVENT_TYPES)

    op.create_table(
        "automation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "automation_execution_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("automation_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(191), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"event_type IN ({event_enum})",
            name="ck_automation_events_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','processed','failed','dead_letter',"
            "'suppressed')",
            name="ck_automation_events_status",
        ),
        sa.CheckConstraint(
            "automation_depth >= 0 AND automation_depth <= 32",
            name="ck_automation_events_depth",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_automation_events_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_automation_events_dequeue",
        "automation_events",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_index(
        "ix_automation_events_tenant_type",
        "automation_events",
        ["tenant_id", "event_type", "created_at"],
    )

    op.create_table(
        "automation_workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("trigger_event", sa.String(64), nullable=False),
        sa.Column(
            "active_version_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','DISABLED','ARCHIVED')",
            name="ck_automation_workflows_status",
        ),
        sa.CheckConstraint(
            f"trigger_event IN ({event_enum})",
            name="ck_automation_workflows_trigger",
        ),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_automation_workflows_tenant_name"
        ),
    )
    op.create_index(
        "ix_automation_workflows_tenant_status",
        "automation_workflows",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_automation_workflows_tenant_trigger",
        "automation_workflows",
        ["tenant_id", "trigger_event", "status"],
    )

    op.create_table(
        "automation_workflow_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column(
            "definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','SUPERSEDED')",
            name="ck_automation_workflow_versions_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_automation_workflow_versions_num"),
        sa.UniqueConstraint(
            "workflow_id",
            "version",
            name="uq_automation_workflow_versions_num",
        ),
    )
    op.create_index(
        "ix_automation_workflow_versions_workflow",
        "automation_workflow_versions",
        ["tenant_id", "workflow_id", "version"],
    )
    op.create_foreign_key(
        "fk_automation_workflows_active_version",
        "automation_workflows",
        "automation_workflow_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "automation_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_workflow_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("automation_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','PARTIAL_SUCCESS',"
            "'FAILED','CANCELLED','SUPPRESSED')",
            name="ck_automation_executions_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "event_id",
            "workflow_id",
            name="uq_automation_executions_event_workflow",
        ),
    )
    op.create_index(
        "ix_automation_executions_tenant_created",
        "automation_executions",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_automation_executions_workflow",
        "automation_executions",
        ["tenant_id", "workflow_id", "created_at"],
    )
    op.create_index(
        "ix_automation_executions_status",
        "automation_executions",
        ["tenant_id", "status", "created_at"],
    )

    op.create_table(
        "automation_action_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("automation_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_key", sa.String(64), nullable=False),
        sa.Column("action_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(191), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column(
            "result", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','SKIPPED',"
            "'RETRYING')",
            name="ck_automation_action_executions_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_automation_action_executions_idem",
        ),
    )
    op.create_index(
        "ix_automation_action_executions_exec",
        "automation_action_executions",
        ["tenant_id", "execution_id", "action_index"],
    )

    op.create_table(
        "automation_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="automation"),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "source_execution_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(191), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('OPEN','IN_PROGRESS','DONE','CANCELLED')",
            name="ck_automation_tasks_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_automation_tasks_tenant_idem",
        ),
    )
    op.create_index(
        "ix_automation_tasks_tenant_status",
        "automation_tasks",
        ["tenant_id", "status", "created_at"],
    )

    op.create_table(
        "automation_scheduled_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.String(191), nullable=False),
        sa.Column("emitted_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_by", sa.String(128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"event_type IN ({event_enum})",
            name="ck_automation_scheduled_events_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','emitted','cancelled','failed')",
            name="ck_automation_scheduled_events_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_automation_scheduled_events_idem",
        ),
    )
    op.create_index(
        "ix_automation_scheduled_events_due",
        "automation_scheduled_events",
        ["status", "due_at"],
    )


def downgrade() -> None:
    op.drop_table("automation_scheduled_events")
    op.drop_table("automation_tasks")
    op.drop_table("automation_action_executions")
    op.drop_table("automation_executions")
    op.drop_constraint(
        "fk_automation_workflows_active_version",
        "automation_workflows",
        type_="foreignkey",
    )
    op.drop_table("automation_workflow_versions")
    op.drop_table("automation_workflows")
    op.drop_table("automation_events")

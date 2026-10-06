"""Phase 12 Dispatch: technician operational status, assignment history, events, ETA."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0042_dispatch"
down_revision = "0041_appointments_scheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "technician_operational_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "technician_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technicians.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="OFFLINE"),
        sa.Column("status_since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "technician_id",
            name="uq_technician_operational_status_tenant_tech",
        ),
    )
    op.create_index(
        "ix_tech_ops_status_tenant_status",
        "technician_operational_status",
        ["tenant_id", "status"],
    )

    op.create_table(
        "technician_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "technician_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technicians.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.String(32), nullable=True),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_technician_status_history_tenant_tech_created",
        "technician_status_history",
        ["tenant_id", "technician_id", "created_at"],
    )

    op.create_table(
        "job_assignment_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "previous_technician_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technicians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "technician_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technicians.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("idempotency_request_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_job_assignment_history_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_job_assignment_history_tenant_job_created",
        "job_assignment_history",
        ["tenant_id", "job_id", "created_at"],
    )
    op.create_index(
        "ix_job_assignment_history_tenant_tech",
        "job_assignment_history",
        ["tenant_id", "technician_id"],
    )

    op.create_table(
        "dispatch_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_dispatch_events_tenant_created",
        "dispatch_events",
        ["tenant_id", "created_at", "id"],
    )

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("eta", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("eta_source", sa.String(32), nullable=True))
        batch.add_column(
            sa.Column("eta_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("assigned_by", sa.String(255), nullable=True))

    # Idempotent backfill: OFFLINE for every technician without a status row.
    op.execute(
        sa.text(
            """
            INSERT INTO technician_operational_status (
                id, tenant_id, technician_id, status, status_since, updated_by, updated_at
            )
            SELECT
                gen_random_uuid(),
                t.tenant_id,
                t.id,
                CASE WHEN t.is_active THEN 'AVAILABLE' ELSE 'OFFLINE' END,
                NOW(),
                'migration:0042_dispatch',
                NOW()
            FROM technicians t
            WHERE NOT EXISTS (
                SELECT 1 FROM technician_operational_status s
                WHERE s.tenant_id = t.tenant_id AND s.technician_id = t.id
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("assigned_by")
        batch.drop_column("assigned_at")
        batch.drop_column("eta_updated_at")
        batch.drop_column("eta_source")
        batch.drop_column("eta")
    op.drop_table("dispatch_events")
    op.drop_table("job_assignment_history")
    op.drop_table("technician_status_history")
    op.drop_table("technician_operational_status")

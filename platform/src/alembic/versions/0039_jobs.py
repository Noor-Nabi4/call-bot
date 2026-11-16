"""Phase 10 Job Management: extend jobs + status history, counters, attachments."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0039_jobs"
down_revision = "0038_orders_hardening"
branch_labels = None
depends_on = None

_STATUS_MAP = {
    "new": "NEW",
    "scheduled": "SCHEDULED",
    "dispatched": "DISPATCHED",
    "in_progress": "IN_PROGRESS",
    "completed": "COMPLETED",
    "canceled": "CANCELLED",
    "cancelled": "CANCELLED",
}


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_pg else sa.String(36)

    op.create_table(
        "job_number_counters",
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
        sa.UniqueConstraint("tenant_id", name="uq_job_number_counters_tenant"),
    )

    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("job_number", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("location_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("service_id", uuid_type, nullable=True))
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "priority",
                sa.String(length=16),
                nullable=False,
                server_default="MEDIUM",
            )
        )
        batch.add_column(sa.Column("created_by", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("updated_by", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("idempotency_key", sa.String(length=128), nullable=True)
        )

    # Migrate legacy lowercase statuses → Phase 10 uppercase.
    for old, new in _STATUS_MAP.items():
        op.execute(
            sa.text(
                "UPDATE jobs SET status = :new WHERE lower(status) = :old"
            ).bindparams(new=new, old=old)
        )

    # Backfill job_number from reference_code when possible; else JOB-legacy-{n}.
    if is_pg:
        op.execute(
            sa.text(
                """
                WITH numbered AS (
                  SELECT id,
                         COALESCE(
                           NULLIF(reference_code, ''),
                           'JOB-' || lpad(
                             CAST(row_number() OVER (
                               PARTITION BY tenant_id ORDER BY created_at, id
                             ) AS text),
                             6, '0'
                           )
                         ) AS num
                  FROM jobs
                  WHERE job_number IS NULL
                )
                UPDATE jobs SET job_number = numbered.num
                FROM numbered WHERE jobs.id = numbered.id
                """
            )
        )
        op.execute(
            sa.text(
                """
                INSERT INTO job_number_counters (tenant_id, last_value, updated_at)
                SELECT tenant_id,
                       COALESCE(MAX(
                         CASE
                           WHEN job_number ~ '^JOB-[0-9]+$'
                           THEN CAST(substring(job_number FROM 5) AS integer)
                           ELSE 0
                         END
                       ), 0),
                       CURRENT_TIMESTAMP
                FROM jobs
                GROUP BY tenant_id
                ON CONFLICT (tenant_id) DO UPDATE
                SET last_value = GREATEST(
                  job_number_counters.last_value, EXCLUDED.last_value
                )
                """
            )
        )
    else:
        op.execute(
            sa.text(
                "UPDATE jobs SET job_number = reference_code WHERE job_number IS NULL"
            )
        )
        op.execute(
            sa.text(
                "UPDATE jobs SET job_number = 'JOB-' || substr(hex(randomblob(3)), 1, 6) "
                "WHERE job_number IS NULL OR job_number = ''"
            )
        )

    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "job_number", existing_type=sa.String(length=32), nullable=False
        )
        batch.create_foreign_key(
            "fk_jobs_location_id",
            "customer_locations",
            ["location_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_jobs_service_id",
            "services",
            ["service_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint(
            "uq_jobs_tenant_job_number", ["tenant_id", "job_number"]
        )
        batch.create_unique_constraint(
            "uq_jobs_tenant_idempotency", ["tenant_id", "idempotency_key"]
        )
        batch.create_check_constraint(
            "ck_jobs_priority",
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')",
        )
        batch.create_check_constraint(
            "ck_jobs_status",
            "status IN ("
            "'NEW','SCHEDULED','CONFIRMED','DISPATCHED','EN_ROUTE','ARRIVED',"
            "'IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW')",
        )

    op.create_index("ix_jobs_tenant_job_number", "jobs", ["tenant_id", "job_number"])
    op.create_index("ix_jobs_tenant_priority", "jobs", ["tenant_id", "priority"])
    op.create_index(
        "ix_jobs_tenant_scheduled_start", "jobs", ["tenant_id", "scheduled_starts_at"]
    )
    op.create_index("ix_jobs_tenant_customer", "jobs", ["tenant_id", "customer_id"])
    op.create_index("ix_jobs_tenant_location", "jobs", ["tenant_id", "location_id"])
    op.create_index("ix_jobs_tenant_service", "jobs", ["tenant_id", "service_id"])
    op.create_index("ix_jobs_tenant_archived", "jobs", ["tenant_id", "archived_at"])

    op.create_table(
        "job_status_history",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("job_id", uuid_type, nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "to_status IN ("
            "'NEW','SCHEDULED','CONFIRMED','DISPATCHED','EN_ROUTE','ARRIVED',"
            "'IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW')",
            name="ck_job_status_history_to_status",
        ),
    )
    op.create_index(
        "ix_job_status_history_tenant_job",
        "job_status_history",
        ["tenant_id", "job_id"],
    )
    op.create_index(
        "ix_job_status_history_tenant_created",
        "job_status_history",
        ["tenant_id", "created_at"],
    )

    with op.batch_alter_table("job_notes") as batch:
        batch.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("updated_by", sa.String(length=255), nullable=True))

    op.execute(
        sa.text("UPDATE job_notes SET updated_at = created_at WHERE updated_at IS NULL")
    )
    with op.batch_alter_table("job_notes") as batch:
        batch.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )

    op.create_table(
        "job_attachments",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("job_id", uuid_type, nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "object_key", name="uq_job_attachments_tenant_object_key"
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_job_attachments_size"),
    )
    op.create_index(
        "ix_job_attachments_tenant_job", "job_attachments", ["tenant_id", "job_id"]
    )


def downgrade() -> None:
    op.drop_table("job_attachments")
    with op.batch_alter_table("job_notes") as batch:
        batch.drop_column("updated_by")
        batch.drop_column("archived_at")
        batch.drop_column("updated_at")
    op.drop_table("job_status_history")
    op.drop_index("ix_jobs_tenant_archived", table_name="jobs")
    op.drop_index("ix_jobs_tenant_service", table_name="jobs")
    op.drop_index("ix_jobs_tenant_location", table_name="jobs")
    op.drop_index("ix_jobs_tenant_customer", table_name="jobs")
    op.drop_index("ix_jobs_tenant_scheduled_start", table_name="jobs")
    op.drop_index("ix_jobs_tenant_priority", table_name="jobs")
    op.drop_index("ix_jobs_tenant_job_number", table_name="jobs")
    with op.batch_alter_table("jobs") as batch:
        batch.drop_constraint("ck_jobs_status", type_="check")
        batch.drop_constraint("ck_jobs_priority", type_="check")
        batch.drop_constraint("uq_jobs_tenant_idempotency", type_="unique")
        batch.drop_constraint("uq_jobs_tenant_job_number", type_="unique")
        batch.drop_constraint("fk_jobs_service_id", type_="foreignkey")
        batch.drop_constraint("fk_jobs_location_id", type_="foreignkey")
        batch.drop_column("idempotency_key")
        batch.drop_column("archived_at")
        batch.drop_column("cancelled_at")
        batch.drop_column("completed_at")
        batch.drop_column("updated_by")
        batch.drop_column("created_by")
        batch.drop_column("priority")
        batch.drop_column("description")
        batch.drop_column("service_id")
        batch.drop_column("location_id")
        batch.drop_column("job_number")
    op.drop_table("job_number_counters")

"""Phase 11 Appointments & Scheduling: extend appointments + availability tables."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0041_appointments_scheduling"
down_revision = "0040_jobs_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- appointment number counters ---
    op.create_table(
        "appointment_number_counters",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", name="uq_appointment_number_counters_tenant"),
    )

    # --- extend tenant_schedule_settings ---
    with op.batch_alter_table("tenant_schedule_settings") as batch:
        batch.add_column(
            sa.Column(
                "emergency_weekly_hours",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )

    op.create_table(
        "business_holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "is_full_day", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "holiday_date", name="uq_business_holidays_tenant_date"
        ),
    )
    op.create_index(
        "ix_business_holidays_tenant_id", "business_holidays", ["tenant_id"]
    )

    # --- skills / service areas ---
    op.create_table(
        "skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_skills_tenant_key"),
    )
    op.create_index("ix_skills_tenant_id", "skills", ["tenant_id"])

    op.create_table(
        "service_areas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("match_type", sa.String(length=32), nullable=False),
        sa.Column("match_value", sa.String(length=128), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_service_areas_tenant_key"),
    )
    op.create_index("ix_service_areas_tenant_id", "service_areas", ["tenant_id"])

    op.create_table(
        "technician_skills",
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
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "technician_id",
            "skill_id",
            name="uq_technician_skills_tenant_tech_skill",
        ),
    )
    op.create_index(
        "ix_technician_skills_tenant_tech",
        "technician_skills",
        ["tenant_id", "technician_id"],
    )

    op.create_table(
        "service_required_skills",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "skill_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "service_id",
            "skill_id",
            name="uq_service_required_skills_tenant_svc_skill",
        ),
    )

    op.create_table(
        "technician_service_areas",
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
        sa.Column(
            "service_area_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "technician_id",
            "service_area_id",
            name="uq_technician_service_areas_tenant_tech_area",
        ),
    )

    # --- technician schedule / breaks / time off ---
    op.create_table(
        "technician_schedule_periods",
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
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_technician_schedule_periods_dow",
        ),
        sa.CheckConstraint(
            "open_time < close_time",
            name="ck_technician_schedule_periods_open_close",
        ),
    )
    op.create_index(
        "ix_technician_schedule_periods_tenant_tech",
        "technician_schedule_periods",
        ["tenant_id", "technician_id"],
    )

    op.create_table(
        "technician_breaks",
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
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_technician_breaks_dow",
        ),
        sa.CheckConstraint(
            "start_time < end_time", name="ck_technician_breaks_start_end"
        ),
    )
    op.create_index(
        "ix_technician_breaks_tenant_tech",
        "technician_breaks",
        ["tenant_id", "technician_id"],
    )

    op.create_table(
        "technician_time_off",
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
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_off_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "starts_at < ends_at", name="ck_technician_time_off_starts_ends"
        ),
    )
    op.create_index(
        "ix_technician_time_off_tenant_tech_starts",
        "technician_time_off",
        ["tenant_id", "technician_id", "starts_at"],
    )

    # --- extend appointments ---
    with op.batch_alter_table("appointments") as batch:
        batch.add_column(sa.Column("appointment_number", sa.String(length=32), nullable=True))
        batch.add_column(
            sa.Column(
                "job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("jobs.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "location_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("customer_locations.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "service_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("services.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "assigned_technician_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("technicians.id", ondelete="SET NULL"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("timezone", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("priority", sa.String(length=16), nullable=False, server_default="NORMAL")
        )
        batch.add_column(
            sa.Column(
                "is_emergency",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch.add_column(sa.Column("idempotency_request_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("created_by", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("updated_by", sa.String(length=255), nullable=True))

    # Backfill duration and normalize status to UPPERCASE.
    op.execute(
        sa.text(
            """
            UPDATE appointments
            SET duration_minutes = GREATEST(
                1,
                CAST(EXTRACT(EPOCH FROM (ends_at - starts_at)) / 60 AS INTEGER)
            )
            WHERE duration_minutes IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE appointments SET status = UPPER(REPLACE(status, '-', '_'))
            """
        )
    )
    op.execute(sa.text("UPDATE appointments SET status = 'CANCELLED' WHERE status = 'CANCELED'"))
    op.execute(
        sa.text(
            """
            UPDATE appointments
            SET appointment_number = confirmation_code
            WHERE appointment_number IS NULL
            """
        )
    )

    with op.batch_alter_table("appointments") as batch:
        batch.alter_column("appointment_number", nullable=False)
        batch.alter_column("duration_minutes", nullable=False)
        batch.create_unique_constraint(
            "uq_appointments_tenant_appointment_number",
            ["tenant_id", "appointment_number"],
        )

    op.create_index(
        "ix_appointments_tenant_technician_starts",
        "appointments",
        ["tenant_id", "assigned_technician_id", "starts_at"],
    )
    op.create_index(
        "ix_appointments_tenant_job", "appointments", ["tenant_id", "job_id"]
    )
    op.create_index(
        "ix_appointments_tenant_service", "appointments", ["tenant_id", "service_id"]
    )
    op.create_index(
        "ix_appointments_tenant_archived", "appointments", ["tenant_id", "archived_at"]
    )

    op.create_table(
        "appointment_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_appointment_status_history_tenant_appt",
        "appointment_status_history",
        ["tenant_id", "appointment_id", "created_at"],
    )

    # PostgreSQL exclusion: no overlapping active appointments for same technician.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        op.execute(
            sa.text(
                """
                ALTER TABLE appointments
                ADD CONSTRAINT excl_appointments_technician_active_range
                EXCLUDE USING gist (
                    tenant_id WITH =,
                    assigned_technician_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (
                    assigned_technician_id IS NOT NULL
                    AND archived_at IS NULL
                    AND status IN ('TENTATIVE', 'SCHEDULED', 'CONFIRMED', 'IN_PROGRESS')
                )
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE appointments "
                "DROP CONSTRAINT IF EXISTS excl_appointments_technician_active_range"
            )
        )

    op.drop_table("appointment_status_history")
    op.drop_index("ix_appointments_tenant_archived", table_name="appointments")
    op.drop_index("ix_appointments_tenant_service", table_name="appointments")
    op.drop_index("ix_appointments_tenant_job", table_name="appointments")
    op.drop_index(
        "ix_appointments_tenant_technician_starts", table_name="appointments"
    )
    with op.batch_alter_table("appointments") as batch:
        batch.drop_constraint(
            "uq_appointments_tenant_appointment_number", type_="unique"
        )
        for col in (
            "updated_by",
            "created_by",
            "archived_at",
            "completed_at",
            "cancelled_at",
            "idempotency_request_hash",
            "is_emergency",
            "priority",
            "timezone",
            "duration_minutes",
            "assigned_technician_id",
            "service_id",
            "location_id",
            "job_id",
            "appointment_number",
        ):
            batch.drop_column(col)

    op.drop_table("technician_time_off")
    op.drop_table("technician_breaks")
    op.drop_table("technician_schedule_periods")
    op.drop_table("technician_service_areas")
    op.drop_table("service_required_skills")
    op.drop_table("technician_skills")
    op.drop_table("service_areas")
    op.drop_table("skills")
    op.drop_table("business_holidays")
    with op.batch_alter_table("tenant_schedule_settings") as batch:
        batch.drop_column("emergency_weekly_hours")
    op.drop_table("appointment_number_counters")

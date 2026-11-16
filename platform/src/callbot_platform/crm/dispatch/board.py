"""Dispatch board projection (Phase 12) — advisory read model over Jobs + Techs."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.dispatch.constants import DEFAULT_TECHNICIAN_STATUS
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import TERMINAL_STATUSES
from callbot_platform.db.models.dispatch import TechnicianOperationalStatus
from callbot_platform.db.models.jobs import Job, Technician
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository


def business_day_window(day: date, tz_name: str) -> tuple[datetime, datetime]:
    """Half-open [local midnight, next local midnight) as UTC instants."""
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(day, time(0, 0), tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


class DispatchBoardService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = ScheduleSettingsRepository(session)

    def board(
        self,
        tenant_id: UUID,
        *,
        board_date: date | None = None,
        technician_id: UUID | None = None,
        status: str | None = None,
        priority: str | None = None,
        assigned: str | None = None,
        q: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        tz_name = self._settings.effective_timezone(tenant_id) or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz_name = "UTC"
            tz = ZoneInfo("UTC")
        day = board_date or datetime.now(tz).date()
        start_utc, end_utc = business_day_window(day, tz_name)

        tech_q = select(Technician).where(
            Technician.tenant_id == tenant_id, Technician.is_active.is_(True)
        )
        if technician_id is not None:
            tech_q = tech_q.where(Technician.id == technician_id)
        tech_q = tech_q.order_by(Technician.display_name.asc())
        technicians = list(self._session.scalars(tech_q).all())
        tech_ids = [t.id for t in technicians]

        status_rows = (
            list(
                self._session.scalars(
                    select(TechnicianOperationalStatus).where(
                        TechnicianOperationalStatus.tenant_id == tenant_id,
                        TechnicianOperationalStatus.technician_id.in_(tech_ids)
                        if tech_ids
                        else False,
                    )
                ).all()
            )
            if tech_ids
            else []
        )
        status_by_tech = {r.technician_id: r for r in status_rows}

        # Jobs scheduled for the business day OR unscheduled NEW jobs (unassigned pool).
        job_q = (
            select(Job)
            .where(
                Job.tenant_id == tenant_id,
                Job.archived_at.is_(None),
                Job.status.notin_(tuple(TERMINAL_STATUSES)),
                or_(
                    (Job.scheduled_starts_at >= start_utc)
                    & (Job.scheduled_starts_at < end_utc),
                    Job.scheduled_starts_at.is_(None),
                ),
            )
            .options(
                selectinload(Job.customer),
                selectinload(Job.location),
                selectinload(Job.service),
                selectinload(Job.assigned_technician),
            )
            .order_by(Job.priority.desc(), Job.scheduled_starts_at.asc().nulls_last())
            .limit(min(max(limit, 1), 1000))
        )
        if status:
            job_q = job_q.where(Job.status == status.strip().upper())
        if priority:
            job_q = job_q.where(Job.priority == priority.strip().upper())
        if assigned == "assigned":
            job_q = job_q.where(Job.assigned_technician_id.is_not(None))
        elif assigned == "unassigned":
            job_q = job_q.where(Job.assigned_technician_id.is_(None))
        if technician_id is not None:
            job_q = job_q.where(
                or_(
                    Job.assigned_technician_id == technician_id,
                    Job.assigned_technician_id.is_(None),
                )
            )
        if q and q.strip():
            needle = f"%{q.strip()}%"
            from callbot_platform.db.models.crm import Customer

            job_q = job_q.join(Job.customer).where(
                or_(
                    Job.job_number.ilike(needle),
                    Job.service_type.ilike(needle),
                    Job.reference_code.ilike(needle),
                    Customer.name.ilike(needle),
                )
            )

        jobs = list(self._session.scalars(job_q).unique().all())

        tech_payload = []
        for t in technicians:
            ops = status_by_tech.get(t.id)
            tech_payload.append(
                {
                    "id": str(t.id),
                    "display_name": t.display_name,
                    "phone": t.phone,
                    "is_active": t.is_active,
                    "status": ops.status if ops else DEFAULT_TECHNICIAN_STATUS,
                    "status_since": (
                        ops.status_since.isoformat()
                        if ops and ops.status_since
                        else None
                    ),
                }
            )

        def _job_card(job: Job) -> dict[str, Any]:
            cust = job.customer
            loc = job.location
            conflict = False
            return {
                "id": str(job.id),
                "job_number": job.job_number,
                "reference_code": job.reference_code,
                "status": job.status,
                "priority": job.priority,
                "service_type": job.service_type,
                "scheduled_starts_at": (
                    job.scheduled_starts_at.isoformat()
                    if job.scheduled_starts_at
                    else None
                ),
                "scheduled_ends_at": (
                    job.scheduled_ends_at.isoformat() if job.scheduled_ends_at else None
                ),
                "eta": job.eta.isoformat() if getattr(job, "eta", None) else None,
                "eta_source": getattr(job, "eta_source", None),
                "assigned_technician_id": (
                    str(job.assigned_technician_id)
                    if job.assigned_technician_id
                    else None
                ),
                "assigned_at": (
                    job.assigned_at.isoformat()
                    if getattr(job, "assigned_at", None)
                    else None
                ),
                "customer": (
                    {
                        "id": str(cust.id),
                        "name": cust.name,
                        "display_name": getattr(cust, "display_name", None)
                        or cust.name,
                    }
                    if cust
                    else None
                ),
                "location": (
                    {
                        "id": str(loc.id),
                        "address_line_1": loc.address_line_1,
                        "city": loc.city,
                        "postal_code": loc.postal_code,
                    }
                    if loc
                    else None
                ),
                "service": (
                    {"id": str(job.service.id), "name": job.service.name}
                    if job.service
                    else None
                ),
                "conflict": conflict,
            }

        unassigned = [_job_card(j) for j in jobs if j.assigned_technician_id is None]
        assigned_jobs = [
            _job_card(j) for j in jobs if j.assigned_technician_id is not None
        ]

        return {
            "date": day.isoformat(),
            "timezone": tz_name,
            "window_start": start_utc.isoformat(),
            "window_end": end_utc.isoformat(),
            "technicians": tech_payload,
            "unassigned_jobs": unassigned,
            "assigned_jobs": assigned_jobs,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def parse_date(self, value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise CrmError("invalid_date", "date must be YYYY-MM-DD") from exc

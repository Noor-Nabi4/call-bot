"""Technician availability CRUD: schedule periods, breaks, time off, skills,
service areas (Phase 11).

All operations are tenant-scoped and validate the technician belongs to the
tenant before any write. Overlap validation uses half-open intervals
``[start, end)`` consistent with the rest of the scheduling domain.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.jobs import Technician
from callbot_platform.db.models.scheduling import (
    ServiceArea,
    ServiceRequiredSkill,
    Skill,
    TechnicianBreak,
    TechnicianSchedulePeriod,
    TechnicianServiceArea,
    TechnicianSkill,
    TechnicianTimeOff,
)
from callbot_platform.db.models.services.service import Service
from callbot_platform.scheduling.availability import parse_hhmm
from callbot_platform.telephony.audit import write_audit

VALID_MATCH_TYPES = frozenset({"POSTAL_CODE", "CITY", "REGION"})
VALID_TIME_OFF_TYPES = frozenset({"VACATION", "SICK", "PERSONAL", "OTHER"})


def _require_technician(
    session: Session, tenant_id: UUID, technician_id: UUID
) -> Technician:
    tech = session.scalar(
        select(Technician).where(
            Technician.id == technician_id, Technician.tenant_id == tenant_id
        )
    )
    if tech is None:
        raise CrmError("technician_not_found", "Technician not found for tenant")
    return tech


class TechnicianAvailabilityService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Schedule periods ---

    def list_periods(
        self, tenant_id: UUID, technician_id: UUID
    ) -> list[dict[str, Any]]:
        _require_technician(self._session, tenant_id, technician_id)
        rows = self._session.scalars(
            select(TechnicianSchedulePeriod)
            .where(
                TechnicianSchedulePeriod.tenant_id == tenant_id,
                TechnicianSchedulePeriod.technician_id == technician_id,
            )
            .order_by(
                TechnicianSchedulePeriod.day_of_week,
                TechnicianSchedulePeriod.open_time,
            )
        ).all()
        return [self._serialize_period(r) for r in rows]

    def create_period(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        day_of_week: int,
        open_time: str,
        close_time: str,
        actor: str,
    ) -> dict[str, Any]:
        _require_technician(self._session, tenant_id, technician_id)
        if day_of_week < 0 or day_of_week > 6:
            raise CrmError("invalid_day_of_week", "day_of_week must be 0-6 (Mon-Sun)")
        try:
            open_t = parse_hhmm(open_time)
            close_t = parse_hhmm(close_time)
        except ValueError as exc:
            raise CrmError(
                "invalid_time", "open_time/close_time must be HH:MM"
            ) from exc
        if open_t >= close_t:
            raise CrmError("invalid_time", "open_time must be before close_time")

        existing = self._session.scalars(
            select(TechnicianSchedulePeriod).where(
                TechnicianSchedulePeriod.tenant_id == tenant_id,
                TechnicianSchedulePeriod.technician_id == technician_id,
                TechnicianSchedulePeriod.day_of_week == day_of_week,
            )
        ).all()
        for row in existing:
            if open_t < row.close_time and row.open_time < close_t:
                raise CrmError(
                    "period_overlap",
                    "Schedule period overlaps an existing period for that day",
                )

        row = TechnicianSchedulePeriod(
            tenant_id=tenant_id,
            technician_id=technician_id,
            day_of_week=day_of_week,
            open_time=open_t,
            close_time=close_t,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_schedule_period_created",
            resource_ids={
                "technician_id": str(technician_id),
                "period_id": str(row.id),
            },
        )
        return self._serialize_period(row)

    def delete_period(
        self, tenant_id: UUID, technician_id: UUID, period_id: UUID, *, actor: str
    ) -> None:
        _require_technician(self._session, tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianSchedulePeriod).where(
                TechnicianSchedulePeriod.id == period_id,
                TechnicianSchedulePeriod.tenant_id == tenant_id,
                TechnicianSchedulePeriod.technician_id == technician_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Schedule period not found")
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_schedule_period_deleted",
            resource_ids={
                "technician_id": str(technician_id),
                "period_id": str(period_id),
            },
        )

    @staticmethod
    def _serialize_period(row: TechnicianSchedulePeriod) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "technician_id": str(row.technician_id),
            "day_of_week": row.day_of_week,
            "open_time": row.open_time.strftime("%H:%M"),
            "close_time": row.close_time.strftime("%H:%M"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    # --- Breaks ---

    def list_breaks(self, tenant_id: UUID, technician_id: UUID) -> list[dict[str, Any]]:
        _require_technician(self._session, tenant_id, technician_id)
        rows = self._session.scalars(
            select(TechnicianBreak)
            .where(
                TechnicianBreak.tenant_id == tenant_id,
                TechnicianBreak.technician_id == technician_id,
            )
            .order_by(TechnicianBreak.day_of_week, TechnicianBreak.start_time)
        ).all()
        return [self._serialize_break(r) for r in rows]

    def create_break(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        day_of_week: int,
        start_time: str,
        end_time: str,
        label: str | None = None,
        actor: str,
    ) -> dict[str, Any]:
        _require_technician(self._session, tenant_id, technician_id)
        if day_of_week < 0 or day_of_week > 6:
            raise CrmError("invalid_day_of_week", "day_of_week must be 0-6 (Mon-Sun)")
        try:
            start_t = parse_hhmm(start_time)
            end_t = parse_hhmm(end_time)
        except ValueError as exc:
            raise CrmError("invalid_time", "start_time/end_time must be HH:MM") from exc
        if start_t >= end_t:
            raise CrmError("invalid_time", "start_time must be before end_time")

        existing = self._session.scalars(
            select(TechnicianBreak).where(
                TechnicianBreak.tenant_id == tenant_id,
                TechnicianBreak.technician_id == technician_id,
                TechnicianBreak.day_of_week == day_of_week,
            )
        ).all()
        for row in existing:
            if start_t < row.end_time and row.start_time < end_t:
                raise CrmError(
                    "break_overlap", "Break overlaps an existing break for that day"
                )

        row = TechnicianBreak(
            tenant_id=tenant_id,
            technician_id=technician_id,
            day_of_week=day_of_week,
            start_time=start_t,
            end_time=end_t,
            label=(label or "").strip()[:128] or None,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_break_created",
            resource_ids={"technician_id": str(technician_id), "break_id": str(row.id)},
        )
        return self._serialize_break(row)

    def delete_break(
        self, tenant_id: UUID, technician_id: UUID, break_id: UUID, *, actor: str
    ) -> None:
        _require_technician(self._session, tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianBreak).where(
                TechnicianBreak.id == break_id,
                TechnicianBreak.tenant_id == tenant_id,
                TechnicianBreak.technician_id == technician_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Break not found")
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_break_deleted",
            resource_ids={
                "technician_id": str(technician_id),
                "break_id": str(break_id),
            },
        )

    @staticmethod
    def _serialize_break(row: TechnicianBreak) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "technician_id": str(row.technician_id),
            "day_of_week": row.day_of_week,
            "start_time": row.start_time.strftime("%H:%M"),
            "end_time": row.end_time.strftime("%H:%M"),
            "label": row.label,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    # --- Time off ---

    def list_time_off(
        self, tenant_id: UUID, technician_id: UUID
    ) -> list[dict[str, Any]]:
        _require_technician(self._session, tenant_id, technician_id)
        rows = self._session.scalars(
            select(TechnicianTimeOff)
            .where(
                TechnicianTimeOff.tenant_id == tenant_id,
                TechnicianTimeOff.technician_id == technician_id,
            )
            .order_by(TechnicianTimeOff.starts_at.asc())
        ).all()
        return [self._serialize_time_off(r) for r in rows]

    def create_time_off(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        starts_at: datetime,
        ends_at: datetime,
        time_off_type: str,
        reason: str | None = None,
        actor: str,
    ) -> dict[str, Any]:
        _require_technician(self._session, tenant_id, technician_id)
        starts = starts_at if starts_at.tzinfo else starts_at.replace(tzinfo=UTC)
        ends = ends_at if ends_at.tzinfo else ends_at.replace(tzinfo=UTC)
        if starts >= ends:
            raise CrmError("invalid_time_off", "starts_at must be before ends_at")
        kind = (time_off_type or "").strip().upper()
        if kind not in VALID_TIME_OFF_TYPES:
            raise CrmError(
                "invalid_time_off_type",
                f"time_off_type must be one of {sorted(VALID_TIME_OFF_TYPES)}",
            )

        existing = self._session.scalars(
            select(TechnicianTimeOff).where(
                TechnicianTimeOff.tenant_id == tenant_id,
                TechnicianTimeOff.technician_id == technician_id,
                TechnicianTimeOff.starts_at < ends,
                TechnicianTimeOff.ends_at > starts,
            )
        ).all()
        if existing:
            raise CrmError(
                "time_off_overlap", "Time off overlaps an existing time-off entry"
            )

        row = TechnicianTimeOff(
            tenant_id=tenant_id,
            technician_id=technician_id,
            starts_at=starts,
            ends_at=ends,
            time_off_type=kind,
            reason=(reason or "").strip()[:500] or None,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_time_off_created",
            resource_ids={
                "technician_id": str(technician_id),
                "time_off_id": str(row.id),
            },
        )
        return self._serialize_time_off(row)

    def delete_time_off(
        self, tenant_id: UUID, technician_id: UUID, time_off_id: UUID, *, actor: str
    ) -> None:
        _require_technician(self._session, tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianTimeOff).where(
                TechnicianTimeOff.id == time_off_id,
                TechnicianTimeOff.tenant_id == tenant_id,
                TechnicianTimeOff.technician_id == technician_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Time off not found")
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_time_off_deleted",
            resource_ids={
                "technician_id": str(technician_id),
                "time_off_id": str(time_off_id),
            },
        )

    @staticmethod
    def _serialize_time_off(row: TechnicianTimeOff) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "technician_id": str(row.technician_id),
            "starts_at": row.starts_at.isoformat() if row.starts_at else None,
            "ends_at": row.ends_at.isoformat() if row.ends_at else None,
            "time_off_type": row.time_off_type,
            "reason": row.reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    # --- Skills (tenant-level catalog + technician/service links) ---

    def list_skills(
        self, tenant_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        q = select(Skill).where(Skill.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(Skill.archived_at.is_(None))
        q = q.order_by(Skill.name)
        return [self._serialize_skill(r) for r in self._session.scalars(q).all()]

    def create_skill(
        self, tenant_id: UUID, *, key: str, name: str, actor: str
    ) -> dict[str, Any]:
        clean_key = (key or "").strip().lower().replace(" ", "_")
        clean_name = (name or "").strip()
        if not clean_key or not clean_name:
            raise CrmError("invalid_skill", "key and name are required")
        row = Skill(tenant_id=tenant_id, key=clean_key[:64], name=clean_name[:255])
        try:
            # Add inside the nested transaction — see comment in
            # BusinessHoursService.create_holiday for why ordering matters.
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "skill_conflict", "A skill with that key already exists"
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="skill_created",
            resource_ids={"skill_id": str(row.id)},
        )
        return self._serialize_skill(row)

    def archive_skill(
        self, tenant_id: UUID, skill_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._require_skill(tenant_id, skill_id)
        row.archived_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="skill_archived",
            resource_ids={"skill_id": str(skill_id)},
        )
        return self._serialize_skill(row)

    def _require_skill(self, tenant_id: UUID, skill_id: UUID) -> Skill:
        row = self._session.scalar(
            select(Skill).where(Skill.id == skill_id, Skill.tenant_id == tenant_id)
        )
        if row is None:
            raise CrmError("skill_not_found", "Skill not found for tenant")
        return row

    @staticmethod
    def _serialize_skill(row: Skill) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "key": row.key,
            "name": row.name,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        }

    def list_technician_skills(
        self, tenant_id: UUID, technician_id: UUID
    ) -> list[dict[str, Any]]:
        _require_technician(self._session, tenant_id, technician_id)
        rows = self._session.execute(
            select(TechnicianSkill, Skill)
            .join(Skill, Skill.id == TechnicianSkill.skill_id)
            .where(
                TechnicianSkill.tenant_id == tenant_id,
                TechnicianSkill.technician_id == technician_id,
            )
        ).all()
        return [
            {"id": str(link.id), "skill": self._serialize_skill(skill)}
            for link, skill in rows
        ]

    def assign_technician_skill(
        self, tenant_id: UUID, technician_id: UUID, skill_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        _require_technician(self._session, tenant_id, technician_id)
        self._require_skill(tenant_id, skill_id)
        existing = self._session.scalar(
            select(TechnicianSkill).where(
                TechnicianSkill.tenant_id == tenant_id,
                TechnicianSkill.technician_id == technician_id,
                TechnicianSkill.skill_id == skill_id,
            )
        )
        if existing is not None:
            return {"id": str(existing.id)}
        row = TechnicianSkill(
            tenant_id=tenant_id, technician_id=technician_id, skill_id=skill_id
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_skill_assigned",
            resource_ids={
                "technician_id": str(technician_id),
                "skill_id": str(skill_id),
            },
        )
        return {"id": str(row.id)}

    def unassign_technician_skill(
        self, tenant_id: UUID, technician_id: UUID, skill_id: UUID, *, actor: str
    ) -> None:
        _require_technician(self._session, tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianSkill).where(
                TechnicianSkill.tenant_id == tenant_id,
                TechnicianSkill.technician_id == technician_id,
                TechnicianSkill.skill_id == skill_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Technician skill link not found")
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_skill_unassigned",
            resource_ids={
                "technician_id": str(technician_id),
                "skill_id": str(skill_id),
            },
        )

    def set_service_required_skills(
        self, tenant_id: UUID, service_id: UUID, skill_ids: list[UUID], *, actor: str
    ) -> list[dict[str, Any]]:
        service = self._session.scalar(
            select(Service).where(
                Service.id == service_id, Service.tenant_id == tenant_id
            )
        )
        if service is None:
            raise CrmError("service_not_found", "Service not found for tenant")
        for skill_id in skill_ids:
            self._require_skill(tenant_id, skill_id)

        existing = list(
            self._session.scalars(
                select(ServiceRequiredSkill).where(
                    ServiceRequiredSkill.tenant_id == tenant_id,
                    ServiceRequiredSkill.service_id == service_id,
                )
            ).all()
        )
        wanted = set(skill_ids)
        for row in existing:
            if row.skill_id not in wanted:
                self._session.delete(row)
        current_ids = {row.skill_id for row in existing}
        for skill_id in wanted - current_ids:
            self._session.add(
                ServiceRequiredSkill(
                    tenant_id=tenant_id, service_id=service_id, skill_id=skill_id
                )
            )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_required_skills_updated",
            resource_ids={"service_id": str(service_id)},
        )
        return self.list_service_required_skills(tenant_id, service_id)

    def list_service_required_skills(
        self, tenant_id: UUID, service_id: UUID
    ) -> list[dict[str, Any]]:
        rows = self._session.execute(
            select(ServiceRequiredSkill, Skill)
            .join(Skill, Skill.id == ServiceRequiredSkill.skill_id)
            .where(
                ServiceRequiredSkill.tenant_id == tenant_id,
                ServiceRequiredSkill.service_id == service_id,
            )
        ).all()
        return [self._serialize_skill(skill) for _link, skill in rows]

    # --- Service areas (tenant-level catalog + technician links) ---

    def list_service_areas(
        self, tenant_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        q = select(ServiceArea).where(ServiceArea.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(ServiceArea.archived_at.is_(None))
        q = q.order_by(ServiceArea.name)
        return [self._serialize_area(r) for r in self._session.scalars(q).all()]

    def create_service_area(
        self,
        tenant_id: UUID,
        *,
        key: str,
        name: str,
        match_type: str,
        match_value: str,
        actor: str,
    ) -> dict[str, Any]:
        clean_key = (key or "").strip().lower().replace(" ", "_")
        clean_name = (name or "").strip()
        kind = (match_type or "").strip().upper()
        value = (match_value or "").strip()
        if not clean_key or not clean_name or not value:
            raise CrmError(
                "invalid_service_area", "key, name, and match_value are required"
            )
        if kind not in VALID_MATCH_TYPES:
            raise CrmError(
                "invalid_match_type",
                f"match_type must be one of {sorted(VALID_MATCH_TYPES)}",
            )
        row = ServiceArea(
            tenant_id=tenant_id,
            key=clean_key[:64],
            name=clean_name[:255],
            match_type=kind,
            match_value=value[:128],
        )
        try:
            # Add inside the nested transaction — see comment in
            # BusinessHoursService.create_holiday for why ordering matters.
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "service_area_conflict", "A service area with that key already exists"
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_area_created",
            resource_ids={"service_area_id": str(row.id)},
        )
        return self._serialize_area(row)

    def archive_service_area(
        self, tenant_id: UUID, service_area_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._require_service_area(tenant_id, service_area_id)
        row.archived_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_area_archived",
            resource_ids={"service_area_id": str(service_area_id)},
        )
        return self._serialize_area(row)

    def _require_service_area(
        self, tenant_id: UUID, service_area_id: UUID
    ) -> ServiceArea:
        row = self._session.scalar(
            select(ServiceArea).where(
                ServiceArea.id == service_area_id, ServiceArea.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError(
                "service_area_not_found", "Service area not found for tenant"
            )
        return row

    @staticmethod
    def _serialize_area(row: ServiceArea) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "key": row.key,
            "name": row.name,
            "match_type": row.match_type,
            "match_value": row.match_value,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        }

    def list_technician_service_areas(
        self, tenant_id: UUID, technician_id: UUID
    ) -> list[dict[str, Any]]:
        _require_technician(self._session, tenant_id, technician_id)
        rows = self._session.execute(
            select(TechnicianServiceArea, ServiceArea)
            .join(ServiceArea, ServiceArea.id == TechnicianServiceArea.service_area_id)
            .where(
                TechnicianServiceArea.tenant_id == tenant_id,
                TechnicianServiceArea.technician_id == technician_id,
            )
        ).all()
        return [self._serialize_area(area) for _link, area in rows]

    def assign_technician_service_area(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        service_area_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        _require_technician(self._session, tenant_id, technician_id)
        self._require_service_area(tenant_id, service_area_id)
        existing = self._session.scalar(
            select(TechnicianServiceArea).where(
                TechnicianServiceArea.tenant_id == tenant_id,
                TechnicianServiceArea.technician_id == technician_id,
                TechnicianServiceArea.service_area_id == service_area_id,
            )
        )
        if existing is not None:
            return {"id": str(existing.id)}
        row = TechnicianServiceArea(
            tenant_id=tenant_id,
            technician_id=technician_id,
            service_area_id=service_area_id,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_service_area_assigned",
            resource_ids={
                "technician_id": str(technician_id),
                "service_area_id": str(service_area_id),
            },
        )
        return {"id": str(row.id)}

    def unassign_technician_service_area(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        service_area_id: UUID,
        *,
        actor: str,
    ) -> None:
        _require_technician(self._session, tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianServiceArea).where(
                TechnicianServiceArea.tenant_id == tenant_id,
                TechnicianServiceArea.technician_id == technician_id,
                TechnicianServiceArea.service_area_id == service_area_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Technician service area link not found")
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_service_area_unassigned",
            resource_ids={
                "technician_id": str(technician_id),
                "service_area_id": str(service_area_id),
            },
        )

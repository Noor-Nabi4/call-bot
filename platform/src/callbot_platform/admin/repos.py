"""Tenant-scoped admin / analytics repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.db.models import (
    Appointment,
    Call,
    Customer,
    Job,
    TelephonyAuditEvent,
    TenantRetentionSettings,
    TenantUser,
)
from callbot_platform.telephony.audit import write_audit


class AdminError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AdminRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_customers(self, tenant_id: UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .options(selectinload(Customer.phones))
            .order_by(Customer.updated_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "email": c.email,
                "address": c.address,
                "phones": [p.e164 for p in (c.phones or [])],
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in rows
        ]

    def list_calls(self, tenant_id: UUID, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(Call)
            .where(Call.tenant_id == tenant_id)
            .order_by(Call.started_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            {
                "id": str(c.id),
                "room_name": c.room_name,
                "status": c.status,
                "caller_number": c.caller_number,
                "called_number": c.called_number,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "customer_id": str(c.customer_id) if c.customer_id else None,
            }
            for c in rows
        ]

    def list_appointments(
        self, tenant_id: UUID, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(Appointment)
            .where(Appointment.tenant_id == tenant_id)
            .order_by(Appointment.starts_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            {
                "id": str(a.id),
                "confirmation_code": a.confirmation_code,
                "status": a.status,
                "service_type": a.service_type,
                "starts_at": a.starts_at.isoformat() if a.starts_at else None,
                "ends_at": a.ends_at.isoformat() if a.ends_at else None,
                "customer_id": str(a.customer_id),
            }
            for a in rows
        ]

    def metrics_summary(self, tenant_id: UUID, *, days: int = 30) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=max(1, min(days, 365)))
        calls = self._session.scalar(
            select(func.count())
            .select_from(Call)
            .where(Call.tenant_id == tenant_id, Call.started_at >= since)
        )
        jobs = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(Job.tenant_id == tenant_id, Job.created_at >= since)
        )
        completed = self._session.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.tenant_id == tenant_id,
                Job.status == "completed",
                Job.updated_at >= since,
            )
        )
        appts = self._session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == tenant_id, Appointment.created_at >= since)
        )
        customers = self._session.scalar(
            select(func.count())
            .select_from(Customer)
            .where(Customer.tenant_id == tenant_id)
        )
        by_status = dict(
            self._session.execute(
                select(Job.status, func.count())
                .where(Job.tenant_id == tenant_id)
                .group_by(Job.status)
            ).all()
        )
        return {
            "window_days": days,
            "calls": int(calls or 0),
            "appointments": int(appts or 0),
            "jobs": int(jobs or 0),
            "jobs_completed": int(completed or 0),
            "customers": int(customers or 0),
            "jobs_by_status": {str(k): int(v) for k, v in by_status.items()},
        }

    def list_audit(
        self, tenant_id: UUID, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(TelephonyAuditEvent)
            .where(TelephonyAuditEvent.tenant_id == tenant_id)
            .order_by(TelephonyAuditEvent.created_at.desc())
            .limit(max(1, min(limit, 200)))
        ).all()
        return [
            {
                "id": str(r.id),
                "actor": r.actor,
                "action": r.action,
                "resource_ids": r.resource_ids,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def list_users(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(TenantUser)
            .where(TenantUser.tenant_id == tenant_id)
            .order_by(TenantUser.created_at.desc())
        ).all()
        return [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "is_active": u.is_active,
            }
            for u in rows
        ]

    def get_retention(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantRetentionSettings).where(
                TenantRetentionSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            return {
                "tenant_id": str(tenant_id),
                "recording_retention_days": 30,
                "transcript_retention_days": 90,
                "audit_retention_days": 365,
            }
        return self._serialize_retention(row)

    def upsert_retention(
        self,
        tenant_id: UUID,
        *,
        recording_retention_days: int | None = None,
        transcript_retention_days: int | None = None,
        audit_retention_days: int | None = None,
        actor: str = "admin",
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantRetentionSettings).where(
                TenantRetentionSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            row = TenantRetentionSettings(tenant_id=tenant_id)
            self._session.add(row)
        if recording_retention_days is not None:
            row.recording_retention_days = max(0, recording_retention_days)
        if transcript_retention_days is not None:
            row.transcript_retention_days = max(0, transcript_retention_days)
        if audit_retention_days is not None:
            row.audit_retention_days = max(0, audit_retention_days)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="retention_settings_upserted",
            resource_ids={"tenant_id": str(tenant_id)},
        )
        return self._serialize_retention(row)

    def _serialize_retention(self, row: TenantRetentionSettings) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "recording_retention_days": row.recording_retention_days,
            "transcript_retention_days": row.transcript_retention_days,
            "audit_retention_days": row.audit_retention_days,
        }

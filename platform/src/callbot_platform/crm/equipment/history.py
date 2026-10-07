"""Assemble equipment timeline from authoritative domain records."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.equipment import Equipment, EquipmentAttachment
from callbot_platform.db.models.invoices import Invoice
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.orders import Order


class EquipmentHistoryService:
    """
    History is derived — not a duplicate ledger.

    Sources: equipment metadata, equipment attachments, jobs (+ notes/attachments),
    invoices linked to those jobs, order items for same customer near job windows.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def history(
        self,
        tenant_id: UUID,
        equipment_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        equipment = self._session.scalar(
            select(Equipment).where(
                Equipment.id == equipment_id, Equipment.tenant_id == tenant_id
            )
        )
        if equipment is None:
            raise CrmError("not_found", "Equipment not found for tenant")

        items: list[dict[str, Any]] = []

        if equipment.installation_date is not None:
            items.append(
                {
                    "type": "INSTALLATION",
                    "date": equipment.installation_date.isoformat(),
                    "summary": (
                        f"Installed {equipment.manufacturer} {equipment.model}"
                    ),
                    "equipment_id": str(equipment.id),
                }
            )
        if (
            equipment.warranty_start_date is not None
            or equipment.warranty_end_date is not None
        ):
            items.append(
                {
                    "type": "WARRANTY",
                    "date": (
                        equipment.warranty_start_date
                        or equipment.warranty_end_date
                    ).isoformat(),
                    "summary": (
                        f"Warranty "
                        f"{equipment.warranty_start_date or '?'} - "
                        f"{equipment.warranty_end_date or '?'}"
                        + (
                            f" ({equipment.warranty_provider})"
                            if equipment.warranty_provider
                            else ""
                        )
                    ),
                    "equipment_id": str(equipment.id),
                    "warranty_provider": equipment.warranty_provider,
                }
            )

        eq_atts = self._session.scalars(
            select(EquipmentAttachment).where(
                EquipmentAttachment.tenant_id == tenant_id,
                EquipmentAttachment.equipment_id == equipment_id,
                EquipmentAttachment.archived_at.is_(None),
            )
        ).all()
        for att in eq_atts:
            items.append(
                {
                    "type": "PHOTO",
                    "date": att.created_at.isoformat(),
                    "summary": att.filename,
                    "attachment_id": str(att.id),
                    "kind": att.kind,
                    "content_type": att.content_type,
                }
            )

        jobs = list(
            self._session.scalars(
                select(Job)
                .where(
                    Job.tenant_id == tenant_id,
                    Job.equipment_id == equipment_id,
                )
                .options(
                    selectinload(Job.assigned_technician),
                    selectinload(Job.service),
                    selectinload(Job.notes),
                    selectinload(Job.attachments),
                )
                .order_by(Job.created_at.desc())
            ).all()
        )
        job_ids = [j.id for j in jobs]

        invoices_by_job: dict[UUID, list[Invoice]] = {}
        if job_ids:
            for inv in self._session.scalars(
                select(Invoice).where(
                    Invoice.tenant_id == tenant_id,
                    Invoice.job_id.in_(job_ids),
                )
            ).all():
                if inv.job_id is None:
                    continue
                invoices_by_job.setdefault(inv.job_id, []).append(inv)

        for job in jobs:
            event_type = "REPAIR" if "repair" in (job.service_type or "").lower() else "SERVICE"
            tech = None
            if job.assigned_technician is not None:
                tech = job.assigned_technician.display_name
            svc = job.service.name if job.service is not None else job.service_type
            items.append(
                {
                    "type": event_type,
                    "date": (job.completed_at or job.created_at).isoformat(),
                    "job_id": str(job.id),
                    "job_number": job.job_number,
                    "status": job.status,
                    "technician": tech,
                    "service": svc,
                    "summary": job.description or job.service_type,
                }
            )
            for note in job.notes or []:
                if note.archived_at is not None:
                    continue
                items.append(
                    {
                        "type": "TECHNICIAN_NOTE",
                        "date": note.created_at.isoformat(),
                        "job_id": str(job.id),
                        "job_number": job.job_number,
                        "summary": (note.body or "")[:500],
                        "note_id": str(note.id),
                    }
                )
            for att in job.attachments or []:
                if att.archived_at is not None:
                    continue
                items.append(
                    {
                        "type": "PHOTO",
                        "date": att.created_at.isoformat(),
                        "job_id": str(job.id),
                        "job_number": job.job_number,
                        "summary": att.filename,
                        "attachment_id": str(att.id),
                        "source": "job",
                    }
                )
            for inv in invoices_by_job.get(job.id, []):
                if inv.order_id is None:
                    continue
                order = self._session.scalar(
                    select(Order)
                    .where(
                        Order.id == inv.order_id,
                        Order.tenant_id == tenant_id,
                    )
                    .options(selectinload(Order.items))
                )
                if order is None:
                    continue
                for line in order.items or []:
                    items.append(
                        {
                            "type": "PART_USED",
                            "date": (order.created_at).isoformat(),
                            "job_id": str(job.id),
                            "order_id": str(order.id),
                            "summary": line.product_name_snapshot or "Part",
                            "quantity": str(line.quantity),
                            "product_id": (
                                str(line.product_id) if line.product_id else None
                            ),
                        }
                    )

        def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
            return (item.get("date") or "", item.get("type") or "")

        items.sort(key=_sort_key, reverse=True)
        page = min(max(1, limit), 100)
        off = max(0, offset)
        slice_ = items[off : off + page]
        return {
            "equipment_id": str(equipment_id),
            "history": slice_,
            "limit": page,
            "offset": off,
            "total": len(items),
        }

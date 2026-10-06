"""Customer timeline aggregation from authoritative domain tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.customers.cursors import TimelineCursor, parse_timeline_page
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import (
    Appointment,
    Call,
    Customer,
    CustomerNote,
    Job,
    Lead,
    LeadActivity,
    NotificationOutbox,
)
from callbot_platform.db.models.orders import Order, OrderStatusHistory

# Controlled event types — only domains that exist today.
TIMELINE_EVENT_TYPES = frozenset(
    {"CALL", "LEAD", "JOB", "APPOINTMENT", "NOTE", "SMS", "EMAIL", "ORDER"}
)

# Permission keys required per event type (fail closed when denied by caller).
TIMELINE_PERMISSIONS: dict[str, str] = {
    "CALL": "calls.read",
    "LEAD": "leads.read",
    "JOB": "jobs.read",
    "APPOINTMENT": "appointments.read",
    "NOTE": "customers.read",
    "SMS": "appointments.read",
    "EMAIL": "appointments.read",
    "ORDER": "orders.read",
}


class CustomerTimelineService:
    """Aggregates existing domain rows; does not invent commerce events."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_timeline(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        allowed_types: frozenset[str],
        event_type: str | None = None,
        limit: int | None = 50,
        cursor: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if customer is None:
            raise CrmError("not_found", "Customer not found for tenant")

        try:
            page, decoded = parse_timeline_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        types = set(allowed_types) & TIMELINE_EVENT_TYPES
        if event_type is not None:
            normalized = event_type.strip().upper()
            if normalized not in TIMELINE_EVENT_TYPES:
                raise CrmError("invalid_event_type", "Unknown timeline event type")
            if normalized not in types:
                return {"items": [], "next_cursor": None, "limit": page.limit}
            types = {normalized}

        # Bound each source query; merge in memory for the page window only.
        fetch_n = page.limit + 1
        events: list[dict[str, Any]] = []

        if "CALL" in types:
            events.extend(
                self._calls(tenant_id, customer_id, fetch_n, since=since, until=until)
            )
        if "LEAD" in types:
            events.extend(
                self._leads(tenant_id, customer_id, fetch_n, since=since, until=until)
            )
            events.extend(
                self._lead_activities(
                    tenant_id, customer_id, fetch_n, since=since, until=until
                )
            )
        if "ORDER" in types:
            events.extend(
                self._orders(tenant_id, customer_id, fetch_n, since=since, until=until)
            )
            events.extend(
                self._order_status_history(
                    tenant_id, customer_id, fetch_n, since=since, until=until
                )
            )
        if "JOB" in types:
            events.extend(
                self._jobs(tenant_id, customer_id, fetch_n, since=since, until=until)
            )
        if "APPOINTMENT" in types:
            events.extend(
                self._appointments(
                    tenant_id, customer_id, fetch_n, since=since, until=until
                )
            )
        if "NOTE" in types:
            events.extend(
                self._notes(tenant_id, customer_id, fetch_n, since=since, until=until)
            )
        if "SMS" in types or "EMAIL" in types:
            events.extend(
                self._notifications(
                    tenant_id,
                    customer_id,
                    fetch_n,
                    channels={
                        *(["sms"] if "SMS" in types else []),
                        *(["email"] if "EMAIL" in types else []),
                    },
                    since=since,
                    until=until,
                )
            )

        events.sort(
            key=lambda e: (e["_occurred_at"], e["source_key"]),
            reverse=True,
        )

        if decoded is not None:
            filtered: list[dict[str, Any]] = []
            for ev in events:
                if ev["_occurred_at"] < decoded.occurred_at or (
                    ev["_occurred_at"] == decoded.occurred_at
                    and ev["source_key"] < decoded.source_key
                ):
                    filtered.append(ev)
            events = filtered

        page_items = events[: page.limit]
        next_cursor = None
        if len(events) > page.limit and page_items:
            last = page_items[-1]
            next_cursor = TimelineCursor(
                occurred_at=last["_occurred_at"],
                source_key=last["source_key"],
            ).encode()

        for item in page_items:
            item.pop("_occurred_at", None)

        return {
            "items": page_items,
            "next_cursor": next_cursor,
            "limit": page.limit,
        }

    def _calls(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        q = select(Call).where(
            Call.tenant_id == tenant_id, Call.customer_id == customer_id
        )
        if since is not None:
            q = q.where(Call.started_at >= since)
        if until is not None:
            q = q.where(Call.started_at <= until)
        q = q.order_by(Call.started_at.desc(), Call.id.desc()).limit(limit)
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            out.append(
                {
                    "type": "CALL",
                    "id": str(row.id),
                    "timestamp": row.started_at.isoformat(),
                    "title": "Call",
                    "summary": f"Status: {row.status}"
                    + (f" · {row.disposition_code}" if row.disposition_code else ""),
                    "source": "calls",
                    "source_key": f"call:{row.id}",
                    "metadata": {
                        "status": row.status,
                        "caller_number": row.caller_number,
                    },
                    "_occurred_at": row.started_at,
                }
            )
        return out

    def _leads(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        q = select(Lead).where(
            Lead.tenant_id == tenant_id, Lead.customer_id == customer_id
        )
        if since is not None:
            q = q.where(Lead.created_at >= since)
        if until is not None:
            q = q.where(Lead.created_at <= until)
        q = q.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit)
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            out.append(
                {
                    "type": "LEAD",
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": f"Lead · {row.title or row.service_type}",
                    "summary": row.notes or f"Status: {row.status}",
                    "source": "leads",
                    "source_key": f"lead:{row.id}",
                    "metadata": {
                        "status": row.status,
                        "reference_code": row.reference_code,
                        "source": row.source,
                        "priority": row.priority,
                    },
                    "_occurred_at": row.created_at,
                }
            )
        return out

    def _lead_activities(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        """Lead activities for leads linked to this customer (same LEAD RBAC)."""
        lead_ids = select(Lead.id).where(
            Lead.tenant_id == tenant_id, Lead.customer_id == customer_id
        )
        q = select(LeadActivity).where(
            LeadActivity.tenant_id == tenant_id,
            LeadActivity.lead_id.in_(lead_ids),
        )
        if since is not None:
            q = q.where(LeadActivity.created_at >= since)
        if until is not None:
            q = q.where(LeadActivity.created_at <= until)
        q = q.order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc()).limit(
            limit
        )
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            out.append(
                {
                    "type": "LEAD",
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": f"Lead · {row.activity_type}",
                    "summary": row.actor or row.activity_type,
                    "source": "lead_activities",
                    "source_key": f"lead_activity:{row.id}",
                    "metadata": {
                        "activity_type": row.activity_type,
                        "lead_id": str(row.lead_id),
                        **dict(row.metadata_json or {}),
                    },
                    "_occurred_at": row.created_at,
                }
            )
        return out

    def _orders(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        q = select(Order).where(
            Order.tenant_id == tenant_id, Order.customer_id == customer_id
        )
        if since is not None:
            q = q.where(Order.created_at >= since)
        if until is not None:
            q = q.where(Order.created_at <= until)
        q = q.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit)
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            out.append(
                {
                    "type": "ORDER",
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": f"Order · {row.order_number}",
                    "summary": f"Status: {row.status} · Total: {row.total} {row.currency}",
                    "source": "orders",
                    "source_key": f"order:{row.id}",
                    "metadata": {
                        "event": "ORDER_CREATED",
                        "status": row.status,
                        "order_number": row.order_number,
                        "total": str(row.total),
                        "currency": row.currency,
                    },
                    "_occurred_at": row.created_at,
                }
            )
        return out

    def _order_status_history(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        order_ids = select(Order.id).where(
            Order.tenant_id == tenant_id, Order.customer_id == customer_id
        )
        q = select(OrderStatusHistory).where(
            OrderStatusHistory.tenant_id == tenant_id,
            OrderStatusHistory.order_id.in_(order_ids),
            OrderStatusHistory.from_status.is_not(None),
        )
        if since is not None:
            q = q.where(OrderStatusHistory.created_at >= since)
        if until is not None:
            q = q.where(OrderStatusHistory.created_at <= until)
        q = q.order_by(
            OrderStatusHistory.created_at.desc(), OrderStatusHistory.id.desc()
        ).limit(limit)
        out: list[dict[str, Any]] = []
        status_event = {
            "CONFIRMED": "ORDER_CONFIRMED",
            "PROCESSING": "ORDER_PROCESSING",
            "SHIPPED": "ORDER_SHIPPED",
            "DELIVERED": "ORDER_DELIVERED",
            "CANCELLED": "ORDER_CANCELLED",
            "REFUNDED": "ORDER_REFUNDED",
        }
        for row in self._session.scalars(q).all():
            event = status_event.get(row.to_status, "ORDER_STATUS_CHANGED")
            out.append(
                {
                    "type": "ORDER",
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": f"Order · {row.to_status}",
                    "summary": (
                        f"{row.from_status} → {row.to_status}"
                        + (f" · {row.reason}" if row.reason else "")
                    ),
                    "source": "order_status_history",
                    "source_key": f"order_status:{row.id}",
                    "metadata": {
                        "event": event,
                        "order_id": str(row.order_id),
                        "from_status": row.from_status,
                        "to_status": row.to_status,
                    },
                    "_occurred_at": row.created_at,
                }
            )
        return out

    def _jobs(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        q = select(Job).where(
            Job.tenant_id == tenant_id, Job.customer_id == customer_id
        )
        if since is not None:
            q = q.where(Job.created_at >= since)
        if until is not None:
            q = q.where(Job.created_at <= until)
        q = q.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit)
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            out.append(
                {
                    "type": "JOB",
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": f"Job · {row.service_type}",
                    "summary": f"Status: {row.status}",
                    "source": "jobs",
                    "source_key": f"job:{row.id}",
                    "metadata": {"status": row.status},
                    "_occurred_at": row.created_at,
                }
            )
        return out

    def _appointments(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        q = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.customer_id == customer_id,
        )
        if since is not None:
            q = q.where(Appointment.starts_at >= since)
        if until is not None:
            q = q.where(Appointment.starts_at <= until)
        q = q.order_by(Appointment.starts_at.desc(), Appointment.id.desc()).limit(limit)
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            out.append(
                {
                    "type": "APPOINTMENT",
                    "id": str(row.id),
                    "timestamp": row.starts_at.isoformat(),
                    "title": f"Appointment · {row.service_type}",
                    "summary": f"Status: {row.status}",
                    "source": "appointments",
                    "source_key": f"appointment:{row.id}",
                    "metadata": {
                        "status": row.status,
                        "confirmation_code": row.confirmation_code,
                    },
                    "_occurred_at": row.starts_at,
                }
            )
        return out

    def _notes(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        q = select(CustomerNote).where(
            CustomerNote.tenant_id == tenant_id,
            CustomerNote.customer_id == customer_id,
        )
        if since is not None:
            q = q.where(CustomerNote.created_at >= since)
        if until is not None:
            q = q.where(CustomerNote.created_at <= until)
        q = q.order_by(CustomerNote.created_at.desc(), CustomerNote.id.desc()).limit(
            limit
        )
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            body = row.body.strip()
            summary = body if len(body) <= 160 else body[:157] + "..."
            out.append(
                {
                    "type": "NOTE",
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": "Note",
                    "summary": summary,
                    "source": "customer_notes",
                    "source_key": f"note:{row.id}",
                    "metadata": {},
                    "_occurred_at": row.created_at,
                }
            )
        return out

    def _notifications(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        limit: int,
        *,
        channels: set[str],
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict[str, Any]]:
        if not channels:
            return []
        appt_ids = self._session.scalars(
            select(Appointment.id).where(
                Appointment.tenant_id == tenant_id,
                Appointment.customer_id == customer_id,
            )
        ).all()
        if not appt_ids:
            return []
        q = select(NotificationOutbox).where(
            NotificationOutbox.tenant_id == tenant_id,
            NotificationOutbox.appointment_id.in_(list(appt_ids)),
            NotificationOutbox.channel.in_(list(channels)),
        )
        if since is not None:
            q = q.where(NotificationOutbox.created_at >= since)
        if until is not None:
            q = q.where(NotificationOutbox.created_at <= until)
        q = q.order_by(
            NotificationOutbox.created_at.desc(), NotificationOutbox.id.desc()
        ).limit(limit)
        out: list[dict[str, Any]] = []
        for row in self._session.scalars(q).all():
            channel = (row.channel or "").lower()
            etype = (
                "SMS" if channel == "sms" else "EMAIL" if channel == "email" else None
            )
            if etype is None:
                continue
            body = (row.body or "").strip()
            summary = body if len(body) <= 160 else body[:157] + "..."
            out.append(
                {
                    "type": etype,
                    "id": str(row.id),
                    "timestamp": row.created_at.isoformat(),
                    "title": f"{etype.title()} notification",
                    "summary": summary,
                    "source": "notification_outbox",
                    "source_key": f"notification:{row.id}",
                    "metadata": {
                        "status": row.status,
                        "channel": row.channel,
                        "appointment_id": str(row.appointment_id)
                        if row.appointment_id
                        else None,
                    },
                    "_occurred_at": row.created_at,
                }
            )
        return out

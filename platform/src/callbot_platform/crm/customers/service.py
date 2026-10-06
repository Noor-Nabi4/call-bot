"""Customer domain service — staff/AI-facing API over the relational Customer model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.customers.locations import CustomerLocationService
from callbot_platform.crm.customers.normalize import normalize_email
from callbot_platform.crm.customers.search import CustomerSearchService
from callbot_platform.crm.customers.serialize import (
    serialize_customer,
    serialize_note,
    serialize_tag,
)
from callbot_platform.crm.customers.status import (
    CUSTOMER_STATUSES,
    DEFAULT_CUSTOMER_STATUS,
)
from callbot_platform.crm.customers.timeline import (
    TIMELINE_PERMISSIONS,
    CustomerTimelineService,
)
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import (
    Customer,
    CustomerNote,
    CustomerPhone,
    CustomerTag,
    CustomerTagLink,
)
from callbot_platform.domain.phone import normalize_e164
from callbot_platform.telephony.audit import write_audit


def _trim(value: str | None, *, max_len: int, field: str) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise CrmError(f"invalid_{field}", f"{field} is too long")
    return cleaned


def _derive_display_name(
    *,
    display_name: str | None,
    first_name: str | None,
    last_name: str | None,
    name: str | None,
) -> str:
    if display_name:
        return display_name
    if name:
        return name
    parts = [p for p in (first_name, last_name) if p]
    if parts:
        return " ".join(parts)
    raise CrmError("invalid_name", "Customer name is required")


class CustomerService:
    """Application service for Customer CRM (RBAC enforced at the route layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.locations = CustomerLocationService(session)
        self._search = CustomerSearchService(session)
        self._timeline = CustomerTimelineService(session)

    # --- AI-compatible aliases ---

    def find_customer(self, tenant_id: UUID, phone: str) -> dict[str, Any] | None:
        return self.lookup_by_phone(tenant_id, phone)

    def search_customers(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search(tenant_id, **kwargs)

    def get_customer(
        self, tenant_id: UUID, customer_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.get(tenant_id, customer_id, **kwargs)

    def get_customer_locations(
        self, tenant_id: UUID, customer_id: UUID, **kwargs: Any
    ) -> list[dict[str, Any]]:
        return self.locations.list_locations(tenant_id, customer_id, **kwargs)

    def get_customer_timeline(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        allowed_types: frozenset[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self._timeline.get_timeline(
            tenant_id, customer_id, allowed_types=allowed_types, **kwargs
        )

    def create_customer(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.create(tenant_id, **kwargs)

    def update_customer(
        self, tenant_id: UUID, customer_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.update(tenant_id, customer_id, **kwargs)

    # --- Core CRUD ---

    def lookup_by_phone(self, tenant_id: UUID, phone: str) -> dict[str, Any] | None:
        e164 = normalize_e164(phone)
        row = self._session.scalar(
            select(CustomerPhone)
            .where(
                CustomerPhone.tenant_id == tenant_id,
                CustomerPhone.e164 == e164,
            )
            .options(
                selectinload(CustomerPhone.customer).selectinload(Customer.phones),
                selectinload(CustomerPhone.customer)
                .selectinload(Customer.tag_links)
                .selectinload(CustomerTagLink.tag),
            )
        )
        if row is None or row.customer is None:
            return None
        if row.customer.tenant_id != tenant_id:
            return None
        return serialize_customer(row.customer)

    def get(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_locations: bool = False,
        include_archived: bool = True,
    ) -> dict[str, Any]:
        customer = self._load(
            tenant_id,
            customer_id,
            include_locations=include_locations,
            require_active=not include_archived,
        )
        return serialize_customer(customer, include_locations=include_locations)

    def list(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._search.search(
            tenant_id,
            q=None,
            status=status,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return self._search.search(
            tenant_id,
            q=q,
            status=status,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str | None = None,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        address: str | None = None,
        status: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        first = _trim(first_name, max_len=128, field="first_name")
        last = _trim(last_name, max_len=128, field="last_name")
        disp = _trim(display_name, max_len=255, field="display_name")
        legacy_name = _trim(name, max_len=255, field="name")
        display = _derive_display_name(
            display_name=disp, first_name=first, last_name=last, name=legacy_name
        )
        email_norm = normalize_email(email)
        status_val = (status or DEFAULT_CUSTOMER_STATUS).strip().upper()
        if status_val not in CUSTOMER_STATUSES:
            raise CrmError("invalid_status", "Invalid customer status")

        e164: str | None = None
        if phone is not None and str(phone).strip():
            e164 = normalize_e164(phone)
            existing = self._session.scalar(
                select(CustomerPhone).where(
                    CustomerPhone.tenant_id == tenant_id,
                    CustomerPhone.e164 == e164,
                )
            )
            if existing is not None:
                raise CrmError(
                    "phone_conflict",
                    "A customer with this phone already exists for the tenant",
                )

        customer = Customer(
            tenant_id=tenant_id,
            name=display,
            first_name=first,
            last_name=last,
            email=email_norm,
            email_normalized=email_norm,
            address=_trim(address, max_len=4000, field="address"),
            status=status_val,
            notes=_trim(notes, max_len=10000, field="notes"),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(customer)
        self._session.flush()
        if e164:
            self._session.add(
                CustomerPhone(tenant_id=tenant_id, customer_id=customer.id, e164=e164)
            )
        if tags:
            for tag_name in tags:
                self._attach_tag(
                    tenant_id, customer.id, tag_name, actor=actor, flush=False
                )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_created",
            resource_ids={"customer_id": str(customer.id)},
        )
        return self.get(tenant_id, customer.id, include_locations=True)

    def update(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        actor: str = "system",
        **fields: Any,
    ) -> dict[str, Any]:
        customer = self._load(tenant_id, customer_id, require_active=True)
        allowed = {
            "name",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "address",
            "status",
            "notes",
            "phone",
            "tags",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise CrmError("invalid_fields", f"Unknown fields: {sorted(unknown)}")

        if "first_name" in fields:
            customer.first_name = _trim(
                fields["first_name"], max_len=128, field="first_name"
            )
        if "last_name" in fields:
            customer.last_name = _trim(
                fields["last_name"], max_len=128, field="last_name"
            )
        if "display_name" in fields or "name" in fields:
            disp = _trim(
                fields.get("display_name")
                if "display_name" in fields
                else fields.get("name"),
                max_len=255,
                field="display_name",
            )
            if disp:
                customer.name = disp
        elif "first_name" in fields or "last_name" in fields:
            # Re-derive only when display not explicitly set and structured names change.
            if customer.first_name or customer.last_name:
                customer.name = _derive_display_name(
                    display_name=None,
                    first_name=customer.first_name,
                    last_name=customer.last_name,
                    name=customer.name,
                )

        if "email" in fields:
            email_norm = normalize_email(fields["email"])
            customer.email = email_norm
            customer.email_normalized = email_norm
        if "address" in fields:
            customer.address = _trim(fields["address"], max_len=4000, field="address")
        if "notes" in fields:
            customer.notes = _trim(fields["notes"], max_len=10000, field="notes")
        if "status" in fields and fields["status"] is not None:
            status_val = str(fields["status"]).strip().upper()
            if status_val not in CUSTOMER_STATUSES:
                raise CrmError("invalid_status", "Invalid customer status")
            customer.status = status_val
        if (
            "phone" in fields
            and fields["phone"] is not None
            and str(fields["phone"]).strip()
        ):
            e164 = normalize_e164(str(fields["phone"]))
            conflict = self._session.scalar(
                select(CustomerPhone).where(
                    CustomerPhone.tenant_id == tenant_id,
                    CustomerPhone.e164 == e164,
                    CustomerPhone.customer_id != customer_id,
                )
            )
            if conflict is not None:
                raise CrmError(
                    "phone_conflict",
                    "A customer with this phone already exists for the tenant",
                )
            existing = self._session.scalar(
                select(CustomerPhone).where(
                    CustomerPhone.tenant_id == tenant_id,
                    CustomerPhone.customer_id == customer_id,
                    CustomerPhone.e164 == e164,
                )
            )
            if existing is None:
                self._session.add(
                    CustomerPhone(
                        tenant_id=tenant_id, customer_id=customer_id, e164=e164
                    )
                )
        if "tags" in fields and fields["tags"] is not None:
            self._replace_tags(
                tenant_id, customer_id, list(fields["tags"]), actor=actor
            )

        customer.updated_by = actor
        customer.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_updated",
            resource_ids={"customer_id": str(customer_id)},
        )
        return self.get(tenant_id, customer_id, include_locations=True)

    def archive(
        self, tenant_id: UUID, customer_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        customer = self._load(tenant_id, customer_id, require_active=False)
        if customer.archived_at is None:
            customer.archived_at = datetime.now(UTC)
            customer.updated_by = actor
            customer.updated_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="customer_archived",
                resource_ids={"customer_id": str(customer_id)},
            )
        return serialize_customer(customer)

    def restore(
        self, tenant_id: UUID, customer_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        customer = self._load(tenant_id, customer_id, require_active=False)
        if customer.archived_at is not None:
            customer.archived_at = None
            customer.updated_by = actor
            customer.updated_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="customer_restored",
                resource_ids={"customer_id": str(customer_id)},
            )
        return serialize_customer(customer)

    # --- Tags ---

    def add_tag(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        tag_name: str,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        self._load(tenant_id, customer_id, require_active=True)
        self._attach_tag(tenant_id, customer_id, tag_name, actor=actor)
        return self.get(tenant_id, customer_id)

    def remove_tag(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        tag_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        self._load(tenant_id, customer_id, require_active=True)
        link = self._session.scalar(
            select(CustomerTagLink).where(
                CustomerTagLink.tenant_id == tenant_id,
                CustomerTagLink.customer_id == customer_id,
                CustomerTagLink.tag_id == tag_id,
            )
        )
        if link is None:
            raise CrmError("not_found", "Tag assignment not found")
        self._session.delete(link)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_tag_removed",
            resource_ids={
                "customer_id": str(customer_id),
                "tag_id": str(tag_id),
            },
        )
        return self.get(tenant_id, customer_id)

    def list_tags(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(CustomerTag)
            .where(CustomerTag.tenant_id == tenant_id)
            .order_by(CustomerTag.name.asc())
            .limit(500)
        ).all()
        return [serialize_tag(t) for t in rows]

    # --- Notes ---

    def add_note(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        body: str,
        *,
        author_user_id: UUID | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        self._load(tenant_id, customer_id, require_active=True)
        cleaned = (body or "").strip()
        if not cleaned:
            raise CrmError("invalid_note", "Note body is required")
        if len(cleaned) > 10000:
            raise CrmError("invalid_note", "Note body is too long")
        note = CustomerNote(
            tenant_id=tenant_id,
            customer_id=customer_id,
            author_user_id=author_user_id,
            body=cleaned,
        )
        self._session.add(note)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_note_added",
            resource_ids={
                "customer_id": str(customer_id),
                "note_id": str(note.id),
            },
        )
        return serialize_note(note)

    # --- Timeline ---

    def timeline(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        allowed_permission_keys: frozenset[str],
        event_type: str | None = None,
        limit: int | None = 50,
        cursor: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, Any]:
        allowed_types: set[str] = set()
        for etype, perm in TIMELINE_PERMISSIONS.items():
            if perm in allowed_permission_keys or (
                etype == "NOTE" and "customers.read" in allowed_permission_keys
            ):
                allowed_types.add(etype)
        return self._timeline.get_timeline(
            tenant_id,
            customer_id,
            allowed_types=frozenset(allowed_types),
            event_type=event_type,
            limit=limit,
            cursor=cursor,
            since=since,
            until=until,
        )

    def find_potential_duplicates(
        self, tenant_id: UUID, customer_id: UUID
    ) -> list[dict[str, Any]]:
        """Suggestion-only duplicate signals (never merges)."""
        customer = self._load(tenant_id, customer_id, require_active=False)
        candidates: dict[UUID, Customer] = {}
        if customer.email_normalized:
            for row in self._session.scalars(
                select(Customer).where(
                    Customer.tenant_id == tenant_id,
                    Customer.id != customer_id,
                    Customer.email_normalized == customer.email_normalized,
                    Customer.archived_at.is_(None),
                )
            ).all():
                candidates[row.id] = row
        phone_e164s = [p.e164 for p in (customer.phones or [])]
        if phone_e164s:
            phone_rows = self._session.scalars(
                select(CustomerPhone)
                .where(
                    CustomerPhone.tenant_id == tenant_id,
                    CustomerPhone.e164.in_(phone_e164s),
                    CustomerPhone.customer_id != customer_id,
                )
                .options(selectinload(CustomerPhone.customer))
            ).all()
            for prow in phone_rows:
                if prow.customer and prow.customer.archived_at is None:
                    candidates[prow.customer.id] = prow.customer
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "email": c.email,
                "phones": [p.e164 for p in (c.phones or [])],
                "signals": [
                    *(
                        ["email"]
                        if customer.email_normalized
                        and c.email_normalized == customer.email_normalized
                        else []
                    ),
                    *(
                        ["phone"]
                        if any(p.e164 in phone_e164s for p in (c.phones or []))
                        else []
                    ),
                ],
            }
            for c in candidates.values()
        ]

    # --- internals ---

    def _load(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_locations: bool = False,
        require_active: bool = False,
    ) -> Customer:
        opts = [
            selectinload(Customer.phones),
            selectinload(Customer.tag_links).selectinload(CustomerTagLink.tag),
        ]
        if include_locations:
            opts.append(selectinload(Customer.locations))
        customer = self._session.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
            .options(*opts)
        )
        if customer is None:
            raise CrmError("not_found", "Customer not found for tenant")
        if require_active and customer.archived_at is not None:
            raise CrmError("customer_archived", "Customer is archived")
        return customer

    def _attach_tag(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        tag_name: str,
        *,
        actor: str,
        flush: bool = True,
    ) -> CustomerTag:
        cleaned = (tag_name or "").strip()
        if not cleaned:
            raise CrmError("invalid_tag", "Tag name is required")
        if len(cleaned) > 64:
            raise CrmError("invalid_tag", "Tag name is too long")
        normalized = cleaned.lower()
        tag = self._session.scalar(
            select(CustomerTag).where(
                CustomerTag.tenant_id == tenant_id,
                CustomerTag.name_normalized == normalized,
            )
        )
        if tag is None:
            tag = CustomerTag(
                tenant_id=tenant_id, name=cleaned, name_normalized=normalized
            )
            self._session.add(tag)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="customer_tag_created",
                resource_ids={"tag_id": str(tag.id)},
            )
        existing = self._session.scalar(
            select(CustomerTagLink).where(
                CustomerTagLink.tenant_id == tenant_id,
                CustomerTagLink.customer_id == customer_id,
                CustomerTagLink.tag_id == tag.id,
            )
        )
        if existing is None:
            self._session.add(
                CustomerTagLink(
                    tenant_id=tenant_id, customer_id=customer_id, tag_id=tag.id
                )
            )
            if flush:
                self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="customer_tag_added",
                resource_ids={
                    "customer_id": str(customer_id),
                    "tag_id": str(tag.id),
                },
            )
        return tag

    def _replace_tags(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        tag_names: list[str],
        *,
        actor: str,
    ) -> None:
        desired = {(t.strip().lower(), t.strip()) for t in tag_names if t and t.strip()}
        existing = list(
            self._session.scalars(
                select(CustomerTagLink)
                .where(
                    CustomerTagLink.tenant_id == tenant_id,
                    CustomerTagLink.customer_id == customer_id,
                )
                .options(selectinload(CustomerTagLink.tag))
            ).all()
        )
        existing_norm = {
            link.tag.name_normalized: link for link in existing if link.tag
        }
        for norm, link in list(existing_norm.items()):
            if norm not in {d[0] for d in desired}:
                self._session.delete(link)
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action="customer_tag_removed",
                    resource_ids={
                        "customer_id": str(customer_id),
                        "tag_id": str(link.tag_id),
                    },
                )
        self._session.flush()
        for norm, display in desired:
            if norm not in existing_norm:
                self._attach_tag(
                    tenant_id, customer_id, display, actor=actor, flush=False
                )
        self._session.flush()

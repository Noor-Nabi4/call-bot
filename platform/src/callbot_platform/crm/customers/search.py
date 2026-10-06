"""Tenant-scoped customer search with ranked, bounded results."""

from __future__ import annotations

import contextlib
import re
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.customers.cursors import CustomerCursor, parse_customer_page
from callbot_platform.crm.customers.normalize import normalize_email
from callbot_platform.crm.customers.serialize import serialize_customer
from callbot_platform.crm.customers.status import CUSTOMER_STATUSES
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import (
    Customer,
    CustomerLocation,
    CustomerPhone,
    CustomerTagLink,
)
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164

# Ranking weights (lower is better). Documented for deterministic ordering.
_RANK_EXACT_PHONE = 1
_RANK_EXACT_EMAIL = 2
_RANK_EXACT_NAME = 3
_RANK_PREFIX_NAME = 4
_RANK_FUZZY_NAME = 5
_RANK_ADDRESS = 6

_DIGITS_RE = re.compile(r"\D+")


def _phone_candidates(query_text: str) -> list[str]:
    """Return E.164 values and/or digit suffixes to probe (exact first)."""
    out: list[str] = []
    with contextlib.suppress(PhoneNumberError):
        out.append(normalize_e164(query_text))
    digits = _DIGITS_RE.sub("", query_text)
    if len(digits) >= 7 and digits not in out:
        # National-format staff input without country code — suffix match.
        out.append(digits)
    return out


class CustomerSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

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
        try:
            page, decoded = parse_customer_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        query_text = (q or "").strip()
        if not query_text:
            return self._list_only(
                tenant_id,
                status=status,
                include_archived=include_archived,
                page_limit=page.limit,
                decoded=decoded,
            )

        ranked: dict[UUID, tuple[int, Customer]] = {}

        for candidate in _phone_candidates(query_text):
            if candidate.startswith("+"):
                phone_filter = CustomerPhone.e164 == candidate
            else:
                phone_filter = CustomerPhone.e164.like(f"%{candidate}")
            phone_rows = self._session.scalars(
                select(CustomerPhone)
                .where(
                    CustomerPhone.tenant_id == tenant_id,
                    phone_filter,
                )
                .options(
                    selectinload(CustomerPhone.customer).selectinload(Customer.phones),
                    selectinload(CustomerPhone.customer)
                    .selectinload(Customer.tag_links)
                    .selectinload(CustomerTagLink.tag),
                )
                .limit(page.limit * 2)
            ).all()
            for prow in phone_rows:
                cust = prow.customer
                if cust is None or cust.tenant_id != tenant_id:
                    continue
                if not include_archived and cust.archived_at is not None:
                    continue
                if status and cust.status != status.strip().upper():
                    continue
                ranked[cust.id] = (_RANK_EXACT_PHONE, cust)

        try:
            email_norm = normalize_email(query_text)
        except CrmError:
            email_norm = None
        if email_norm:
            email_rows = self._session.scalars(
                self._base_customer_query(
                    tenant_id,
                    status=status,
                    include_archived=include_archived,
                ).where(Customer.email_normalized == email_norm)
            ).all()
            for cust in email_rows:
                ranked.setdefault(cust.id, (_RANK_EXACT_EMAIL, cust))

        like = f"%{query_text.lower()}%"
        prefix = f"{query_text.lower()}%"

        name_rows = self._session.scalars(
            self._base_customer_query(
                tenant_id,
                status=status,
                include_archived=include_archived,
            )
            .where(
                or_(
                    func.lower(Customer.name) == query_text.lower(),
                    func.lower(Customer.name).like(prefix),
                    func.lower(Customer.name).like(like),
                    and_(
                        Customer.first_name.is_not(None),
                        func.lower(Customer.first_name).like(like),
                    ),
                    and_(
                        Customer.last_name.is_not(None),
                        func.lower(Customer.last_name).like(like),
                    ),
                )
            )
            .limit(page.limit * 3)
        ).all()
        for cust in name_rows:
            if cust.id in ranked:
                continue
            name_l = (cust.name or "").lower()
            if name_l == query_text.lower():
                ranked[cust.id] = (_RANK_EXACT_NAME, cust)
            elif name_l.startswith(query_text.lower()):
                ranked[cust.id] = (_RANK_PREFIX_NAME, cust)
            else:
                ranked[cust.id] = (_RANK_FUZZY_NAME, cust)

        addr_cust_ids = list(
            self._session.scalars(
                select(CustomerLocation.customer_id)
                .where(
                    CustomerLocation.tenant_id == tenant_id,
                    CustomerLocation.archived_at.is_(None),
                    or_(
                        func.lower(CustomerLocation.address_line_1).like(like),
                        and_(
                            CustomerLocation.address_line_2.is_not(None),
                            func.lower(CustomerLocation.address_line_2).like(like),
                        ),
                        and_(
                            CustomerLocation.city.is_not(None),
                            func.lower(CustomerLocation.city).like(like),
                        ),
                        and_(
                            CustomerLocation.state.is_not(None),
                            func.lower(CustomerLocation.state).like(like),
                        ),
                        and_(
                            CustomerLocation.postal_code.is_not(None),
                            func.lower(CustomerLocation.postal_code).like(like),
                        ),
                        and_(
                            CustomerLocation.country.is_not(None),
                            func.lower(CustomerLocation.country).like(like),
                        ),
                    ),
                )
                .limit(page.limit * 3)
            ).all()
        )
        if addr_cust_ids:
            addr_customers = self._session.scalars(
                self._base_customer_query(
                    tenant_id,
                    status=status,
                    include_archived=include_archived,
                ).where(Customer.id.in_(addr_cust_ids))
            ).all()
            for cust in addr_customers:
                ranked.setdefault(cust.id, (_RANK_ADDRESS, cust))

        legacy_addr = self._session.scalars(
            self._base_customer_query(
                tenant_id,
                status=status,
                include_archived=include_archived,
            )
            .where(
                Customer.address.is_not(None),
                func.lower(cast(Customer.address, String)).like(like),
            )
            .limit(page.limit * 2)
        ).all()
        for cust in legacy_addr:
            ranked.setdefault(cust.id, (_RANK_ADDRESS, cust))

        items = sorted(
            ranked.values(),
            key=lambda pair: (
                pair[0],
                -(pair[1].updated_at.timestamp() if pair[1].updated_at else 0),
                str(pair[1].id),
            ),
        )
        ordered = [c for _, c in items]
        if decoded is not None:
            found = False
            after: list[Customer] = []
            for cust in ordered:
                if found:
                    after.append(cust)
                elif cust.id == decoded.id:
                    found = True
            ordered = after if found else ordered

        page_items = ordered[: page.limit]
        next_cursor = None
        if len(ordered) > page.limit and page_items:
            last = page_items[-1]
            next_cursor = CustomerCursor(
                updated_at=last.updated_at, id=last.id
            ).encode()

        return {
            "customers": [serialize_customer(c) for c in page_items],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }

    def _list_only(
        self,
        tenant_id: UUID,
        *,
        status: str | None,
        include_archived: bool,
        page_limit: int,
        decoded: CustomerCursor | None,
    ) -> dict[str, Any]:
        q = self._base_customer_query(
            tenant_id, status=status, include_archived=include_archived
        )
        if decoded is not None:
            q = q.where(
                or_(
                    Customer.updated_at < decoded.updated_at,
                    and_(
                        Customer.updated_at == decoded.updated_at,
                        Customer.id < decoded.id,
                    ),
                )
            )
        q = q.order_by(Customer.updated_at.desc(), Customer.id.desc()).limit(
            page_limit + 1
        )
        rows = list(self._session.scalars(q).all())
        next_cursor = None
        if len(rows) > page_limit:
            last = rows[page_limit - 1]
            next_cursor = CustomerCursor(
                updated_at=last.updated_at, id=last.id
            ).encode()
            rows = rows[:page_limit]
        return {
            "customers": [serialize_customer(c) for c in rows],
            "next_cursor": next_cursor,
            "limit": page_limit,
        }

    def _base_customer_query(
        self,
        tenant_id: UUID,
        *,
        status: str | None,
        include_archived: bool,
    ):
        q = (
            select(Customer)
            .where(Customer.tenant_id == tenant_id)
            .options(
                selectinload(Customer.phones),
                selectinload(Customer.tag_links).selectinload(CustomerTagLink.tag),
            )
        )
        if not include_archived:
            q = q.where(Customer.archived_at.is_(None))
        if status is not None:
            normalized = status.strip().upper()
            if normalized not in CUSTOMER_STATUSES:
                raise CrmError("invalid_status", "Invalid customer status filter")
            q = q.where(Customer.status == normalized)
        return q

"""Authoritative service price resolution.

Precedence (deterministic):
  1. Active tenant/organization override for (pricebook, service) at time
  2. Active pricebook item for (pricebook, service) at time
  3. Service.base_price (source=service_base)
  4. no_price when service has no base price

Fallback when pricebook item is missing/expired:
  → service base price if set, else no_price.

Effective ranges are inclusive [effective_from, effective_until]
(NULL bound = unbounded). Selection among candidates is ordered by
effective_from DESC NULLS LAST, then id DESC (at most one after overlap rules).

Does not mutate inventory. Does not cross tenant boundaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.constants import (
    PRICE_SOURCE_NO_PRICE,
    PRICE_SOURCE_OVERRIDE,
    PRICE_SOURCE_PRICEBOOK_ITEM,
    PRICE_SOURCE_SERVICE_BASE,
    PricingType,
)
from callbot_platform.crm.services.normalize import is_effective_at, money_to_str
from callbot_platform.db.models.services import (
    Pricebook,
    PricebookItem,
    PricebookOverride,
    Service,
)


class PricingService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve_service_price(
        self,
        tenant_id: UUID,
        *,
        service_id: UUID,
        pricebook_id: UUID | None = None,
        at: datetime | None = None,
        allow_archived_service: bool = False,
    ) -> dict[str, Any]:
        """Resolve effective price for a service.

        If pricebook_id is omitted, uses the tenant default pricebook when
        one exists and is effective; otherwise falls back to service base.
        """
        at_time = at or datetime.now(UTC)
        if at_time.tzinfo is None:
            at_time = at_time.replace(tzinfo=UTC)

        service = self._load_service(
            tenant_id, service_id, require_active=not allow_archived_service
        )
        pricebook = self._resolve_pricebook(
            tenant_id, pricebook_id=pricebook_id, at=at_time
        )

        if pricebook is not None:
            override = self._find_override(
                tenant_id,
                pricebook_id=pricebook.id,
                service_id=service.id,
                at=at_time,
            )
            if override is not None:
                return self._from_override(service, pricebook, override, at_time)

            item = self._find_item(
                tenant_id,
                pricebook_id=pricebook.id,
                service_id=service.id,
                at=at_time,
            )
            if item is not None:
                return self._from_item(service, pricebook, item, at_time)

        return self._from_service_base(service, pricebook, at_time)

    def _load_service(
        self, tenant_id: UUID, service_id: UUID, *, require_active: bool
    ) -> Service:
        row = self._session.scalar(
            select(Service).where(
                Service.id == service_id,
                Service.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Service not found for tenant")
        if require_active and (row.archived_at is not None or row.status != "ACTIVE"):
            raise CrmError("not_found", "Service not found for tenant")
        return row

    def _resolve_pricebook(
        self,
        tenant_id: UUID,
        *,
        pricebook_id: UUID | None,
        at: datetime,
    ) -> Pricebook | None:
        if pricebook_id is not None:
            row = self._session.scalar(
                select(Pricebook).where(
                    Pricebook.id == pricebook_id,
                    Pricebook.tenant_id == tenant_id,
                )
            )
            if row is None or row.archived_at is not None:
                raise CrmError("not_found", "Pricebook not found for tenant")
            if row.status != "ACTIVE":
                raise CrmError("pricebook_inactive", "Pricebook is inactive")
            if not is_effective_at(
                at=at,
                effective_from=row.effective_from,
                effective_until=row.effective_until,
            ):
                raise CrmError(
                    "pricebook_not_effective",
                    "Pricebook is not effective at the requested time",
                )
            return row

        row = self._session.scalar(
            select(Pricebook).where(
                Pricebook.tenant_id == tenant_id,
                Pricebook.is_default.is_(True),
                Pricebook.archived_at.is_(None),
                Pricebook.status == "ACTIVE",
            )
        )
        if row is None:
            return None
        if not is_effective_at(
            at=at,
            effective_from=row.effective_from,
            effective_until=row.effective_until,
        ):
            return None
        return row

    @staticmethod
    def _effective_clause(model: type, at: datetime) -> Any:
        return and_(
            or_(model.effective_from.is_(None), model.effective_from <= at),
            or_(model.effective_until.is_(None), model.effective_until >= at),
        )

    def _find_override(
        self,
        tenant_id: UUID,
        *,
        pricebook_id: UUID,
        service_id: UUID,
        at: datetime,
    ) -> PricebookOverride | None:
        return self._session.scalar(
            select(PricebookOverride)
            .where(
                PricebookOverride.tenant_id == tenant_id,
                PricebookOverride.pricebook_id == pricebook_id,
                PricebookOverride.service_id == service_id,
                PricebookOverride.archived_at.is_(None),
                PricebookOverride.status == "ACTIVE",
                self._effective_clause(PricebookOverride, at),
            )
            .order_by(
                PricebookOverride.effective_from.desc().nulls_last(),
                PricebookOverride.id.desc(),
            )
            .limit(1)
        )

    def _find_item(
        self,
        tenant_id: UUID,
        *,
        pricebook_id: UUID,
        service_id: UUID,
        at: datetime,
    ) -> PricebookItem | None:
        return self._session.scalar(
            select(PricebookItem)
            .where(
                PricebookItem.tenant_id == tenant_id,
                PricebookItem.pricebook_id == pricebook_id,
                PricebookItem.service_id == service_id,
                PricebookItem.archived_at.is_(None),
                PricebookItem.status == "ACTIVE",
                self._effective_clause(PricebookItem, at),
            )
            .order_by(
                PricebookItem.effective_from.desc().nulls_last(),
                PricebookItem.id.desc(),
            )
            .limit(1)
        )

    def _from_override(
        self,
        service: Service,
        pricebook: Pricebook,
        override: PricebookOverride,
        at: datetime,
    ) -> dict[str, Any]:
        ptype = override.pricing_type or PricingType.FIXED.value
        return self._payload(
            service=service,
            pricebook=pricebook,
            price=override.override_price,
            pricing_type=ptype,
            source=PRICE_SOURCE_OVERRIDE,
            pricebook_item_id=None,
            override_id=override.id,
            effective_from=override.effective_from,
            effective_until=override.effective_until,
            at=at,
        )

    def _from_item(
        self,
        service: Service,
        pricebook: Pricebook,
        item: PricebookItem,
        at: datetime,
    ) -> dict[str, Any]:
        price = self._amount_for_type(item)
        return self._payload(
            service=service,
            pricebook=pricebook,
            price=price,
            pricing_type=item.pricing_type,
            source=PRICE_SOURCE_PRICEBOOK_ITEM,
            pricebook_item_id=item.id,
            override_id=None,
            effective_from=item.effective_from,
            effective_until=item.effective_until,
            at=at,
            starting_price=item.starting_price,
            hourly_rate=item.hourly_rate,
        )

    def _from_service_base(
        self,
        service: Service,
        pricebook: Pricebook | None,
        at: datetime,
    ) -> dict[str, Any]:
        if service.base_price is None:
            source = PRICE_SOURCE_NO_PRICE
        else:
            source = PRICE_SOURCE_SERVICE_BASE
        return self._payload(
            service=service,
            pricebook=pricebook,
            price=service.base_price,
            pricing_type=service.pricing_type,
            source=source,
            pricebook_item_id=None,
            override_id=None,
            effective_from=None,
            effective_until=None,
            at=at,
        )

    @staticmethod
    def _amount_for_type(item: PricebookItem) -> Decimal | None:
        if item.pricing_type == PricingType.STARTING_AT.value:
            return (
                item.starting_price if item.starting_price is not None else item.price
            )
        if item.pricing_type == PricingType.HOURLY.value:
            return item.hourly_rate if item.hourly_rate is not None else item.price
        if item.pricing_type == PricingType.CUSTOM_QUOTE.value:
            return item.price
        return item.price

    @staticmethod
    def _payload(
        *,
        service: Service,
        pricebook: Pricebook | None,
        price: Decimal | None,
        pricing_type: str,
        source: str,
        pricebook_item_id: UUID | None,
        override_id: UUID | None,
        effective_from: datetime | None,
        effective_until: datetime | None,
        at: datetime,
        starting_price: Decimal | None = None,
        hourly_rate: Decimal | None = None,
    ) -> dict[str, Any]:
        return {
            "service_id": str(service.id),
            "service_name": service.name,
            "service_code": service.code,
            "duration_minutes": service.duration_minutes,
            "pricebook_id": str(pricebook.id) if pricebook else None,
            "pricebook_name": pricebook.name if pricebook else None,
            "pricebook_item_id": (
                str(pricebook_item_id) if pricebook_item_id else None
            ),
            "override_id": str(override_id) if override_id else None,
            "price": money_to_str(price),
            "starting_price": money_to_str(starting_price),
            "hourly_rate": money_to_str(hourly_rate),
            "pricing_type": pricing_type,
            "source": source,
            "effective_from": (effective_from.isoformat() if effective_from else None),
            "effective_until": (
                effective_until.isoformat() if effective_until else None
            ),
            "resolved_at": at.isoformat(),
            "tax_rate": money_to_str(service.tax_rate),
        }

"""Idempotent usage ledger writer."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.billing.usage import calendar_month_bounds
from callbot_platform.billing.usage_ledger.categories import (
    USAGE_TYPE_UNITS,
    AccountingProvenance,
    BillingStatus,
    CostBasis,
    UsageType,
    provenance_to_cost_basis,
)
from callbot_platform.billing.usage_ledger.money import multiply_unit_cost
from callbot_platform.billing.usage_ledger.pricing import (
    UsagePricingCatalog,
    catalog_from_settings,
)
from callbot_platform.db.models.usage_ledger import UsageLedgerEntry

logger = logging.getLogger(__name__)


def billing_period_for(when: datetime) -> str:
    when = when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)
    return f"{when.year:04d}-{when.month:02d}"


class UsageLedgerService:
    def __init__(
        self,
        session: Session,
        *,
        catalog: UsagePricingCatalog | None = None,
    ) -> None:
        self._session = session
        self._catalog = catalog or catalog_from_settings()

    def record(
        self,
        *,
        tenant_id: UUID,
        usage_type: UsageType | str,
        quantity: int,
        idempotency_key: str,
        source_type: str,
        source_id: str,
        occurred_at: datetime | None = None,
        provider: str | None = None,
        provider_reference: str | None = None,
        metadata: dict[str, Any] | None = None,
        usage_provenance: AccountingProvenance
        | str = AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance: AccountingProvenance | str | None = None,
        billing_status: BillingStatus | str | None = None,
        unit_cost_micros_override: int | None = None,
        cost_basis_override: CostBasis | None = None,
        total_cost_micros_override: int | None = None,
        entry_kind: str = "usage",
    ) -> tuple[UsageLedgerEntry, bool]:
        """Insert usage event. Returns (row, created).

        Duplicate idempotency_key for the tenant returns the existing row.
        Historical rows are never rewritten when current pricing changes.
        """
        ut = UsageType(usage_type)
        qty = max(0, int(quantity))
        key = (idempotency_key or "").strip()
        if not key:
            raise ValueError("idempotency_key required")
        if len(key) > 255:
            key = key[:255]
        kind = (entry_kind or "usage").strip().lower()
        if kind not in {"usage", "adjustment"}:
            raise ValueError("entry_kind must be usage or adjustment")

        existing = self._session.scalar(
            select(UsageLedgerEntry).where(
                UsageLedgerEntry.tenant_id == tenant_id,
                UsageLedgerEntry.idempotency_key == key,
            )
        )
        if existing is not None:
            return existing, False

        when = occurred_at or datetime.now(UTC)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)

        price = self._catalog.resolve(ut, at=when)
        unit_cost = (
            unit_cost_micros_override
            if unit_cost_micros_override is not None
            else price.unit_cost_micros
        )

        # Resolve cost provenance / basis.
        if cost_basis_override is not None:
            basis = cost_basis_override
            cost_prov = (
                AccountingProvenance(cost_provenance)
                if cost_provenance is not None
                else None
            )
            if cost_prov is None:
                from callbot_platform.billing.usage_ledger.categories import (
                    cost_basis_to_provenance,
                )

                cost_prov = cost_basis_to_provenance(basis)
        elif cost_provenance is not None:
            cost_prov = AccountingProvenance(cost_provenance)
            basis = provenance_to_cost_basis(cost_prov)
        else:
            basis = price.cost_basis
            from callbot_platform.billing.usage_ledger.categories import (
                cost_basis_to_provenance,
            )

            cost_prov = cost_basis_to_provenance(basis)

        if total_cost_micros_override is not None:
            total = total_cost_micros_override
        elif unit_cost is None or cost_prov == AccountingProvenance.UNAVAILABLE:
            total = None
            basis = CostBasis.NONE
            cost_prov = AccountingProvenance.UNAVAILABLE
        elif basis == CostBasis.NONE:
            total = None
            cost_prov = AccountingProvenance.UNAVAILABLE
        else:
            total = multiply_unit_cost(qty, unit_cost)

        if (
            ut == UsageType.STORAGE
            and unit_cost is not None
            and total is not None
            and cost_prov != AccountingProvenance.UNAVAILABLE
        ):
            gb = bytes_to_billable_gb(qty)
            total = int(gb * unit_cost) if gb > 0 else 0

        usage_prov = AccountingProvenance(usage_provenance)
        bill_status = (
            BillingStatus(billing_status).value if billing_status is not None else None
        )

        meta = dict(metadata or {})
        meta.setdefault("pricing_snapshot", price.snapshot)
        meta["cost_provenance"] = cost_prov.value
        meta["usage_provenance"] = usage_prov.value

        row = UsageLedgerEntry(
            tenant_id=tenant_id,
            usage_type=ut.value,
            quantity=qty,
            unit=USAGE_TYPE_UNITS[ut].value,
            provider=provider,
            provider_reference=provider_reference,
            source_type=source_type,
            source_id=str(source_id),
            idempotency_key=key,
            occurred_at=when,
            billing_period=billing_period_for(when),
            pricing_version=price.pricing_version,
            unit_cost_micros=unit_cost,
            total_cost_micros=total,
            currency=price.currency,
            cost_basis=basis.value,
            usage_provenance=usage_prov.value,
            billing_status=bill_status,
            entry_kind=kind,
            meta_json=meta,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            again = self._session.scalar(
                select(UsageLedgerEntry).where(
                    UsageLedgerEntry.tenant_id == tenant_id,
                    UsageLedgerEntry.idempotency_key == key,
                )
            )
            if again is None:
                raise
            return again, False
        return row, True

    def period_bounds(
        self, *, now: datetime | None = None
    ) -> tuple[datetime, datetime, str]:
        start, end = calendar_month_bounds(now)
        return start, end, billing_period_for(start)


def bytes_to_billable_gb(byte_count: int) -> int:
    """Ceil bytes to whole GiB for configured storage pricing."""
    if byte_count <= 0:
        return 0
    gib = 1024**3
    return (byte_count + gib - 1) // gib

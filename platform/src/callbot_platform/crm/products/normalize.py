"""SKU and money helpers for the product catalog."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.constants import (
    SKU_OWNER_PRODUCT,
    SKU_OWNER_VARIANT,
    WEIGHT_UNITS,
)
from callbot_platform.db.models import CatalogSku

_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MONEY_QUANTUM = Decimal("0.0001")
_TAX_QUANTUM = Decimal("0.0001")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_sku(
    value: str | None, *, required: bool = False
) -> tuple[str | None, str | None]:
    """Return (display_sku, sku_normalized). SKU matching is case-insensitive."""
    if value is None:
        if required:
            raise CrmError("invalid_sku", "SKU is required")
        return None, None
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise CrmError("invalid_sku", "SKU is required")
        return None, None
    if len(cleaned) > 64:
        raise CrmError("invalid_sku", "SKU is too long")
    if not _SKU_RE.match(cleaned):
        raise CrmError(
            "invalid_sku",
            "SKU may contain letters, digits, '.', '_', '-' and must start alphanumerically",
        )
    return cleaned, cleaned.upper()


def parse_money(value: object | None, *, field: str) -> Decimal | None:
    if value is None:
        return None
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CrmError(f"invalid_{field}", f"Invalid {field}") from exc
    if not num.is_finite():
        raise CrmError(f"invalid_{field}", f"Invalid {field}")
    if num < 0:
        raise CrmError(f"invalid_{field}", f"{field} must be non-negative")
    return num.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def parse_tax_rate(value: object | None) -> Decimal | None:
    """Tax rate as percent 0-100 (product-level only; not a tax engine)."""
    if value is None:
        return None
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CrmError("invalid_tax_rate", "Invalid tax rate") from exc
    if num < 0 or num > 100:
        raise CrmError("invalid_tax_rate", "Tax rate must be between 0 and 100")
    return num.quantize(_TAX_QUANTUM, rounding=ROUND_HALF_UP)


def parse_weight(
    weight: object | None, unit: str | None
) -> tuple[Decimal | None, str | None]:
    if weight is None and (unit is None or not str(unit).strip()):
        return None, None
    if weight is None:
        raise CrmError("invalid_weight", "Weight value is required when unit is set")
    try:
        num = Decimal(str(weight))
    except (InvalidOperation, ValueError) as exc:
        raise CrmError("invalid_weight", "Invalid weight") from exc
    if num < 0:
        raise CrmError("invalid_weight", "Weight must be non-negative")
    unit_val = (unit or "KG").strip().upper()
    if unit_val not in WEIGHT_UNITS:
        raise CrmError("invalid_weight_unit", "Weight unit must be KG, G, LB, or OZ")
    return num.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP), unit_val


def slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return (base or "category")[:160]


def money_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SkuRegistry:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(
        self,
        tenant_id: UUID,
        *,
        sku: str,
        sku_normalized: str,
        owner_kind: str,
        owner_id: UUID,
    ) -> None:
        if owner_kind not in {SKU_OWNER_PRODUCT, SKU_OWNER_VARIANT}:
            raise CrmError("invalid_sku_owner", "Invalid SKU owner kind")
        existing = self._session.scalar(
            select(CatalogSku).where(
                CatalogSku.tenant_id == tenant_id,
                CatalogSku.sku_normalized == sku_normalized,
            )
        )
        if existing is not None:
            if existing.owner_kind == owner_kind and existing.owner_id == owner_id:
                existing.sku = sku
                return
            raise CrmError("sku_conflict", "SKU already in use for this tenant")
        row = CatalogSku(
            tenant_id=tenant_id,
            sku=sku,
            sku_normalized=sku_normalized,
            owner_kind=owner_kind,
            owner_id=owner_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "sku_conflict", "SKU already in use for this tenant"
            ) from exc

    def release(
        self,
        tenant_id: UUID,
        *,
        owner_kind: str,
        owner_id: UUID,
    ) -> None:
        row = self._session.scalar(
            select(CatalogSku).where(
                CatalogSku.tenant_id == tenant_id,
                CatalogSku.owner_kind == owner_kind,
                CatalogSku.owner_id == owner_id,
            )
        )
        if row is not None:
            self._session.delete(row)

    def transfer(
        self,
        tenant_id: UUID,
        *,
        owner_kind: str,
        owner_id: UUID,
        sku: str | None,
        sku_normalized: str | None,
    ) -> None:
        self.release(tenant_id, owner_kind=owner_kind, owner_id=owner_id)
        if sku and sku_normalized:
            self.claim(
                tenant_id,
                sku=sku,
                sku_normalized=sku_normalized,
                owner_kind=owner_kind,
                owner_id=owner_id,
            )

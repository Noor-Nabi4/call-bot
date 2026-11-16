"""Customer location CRUD with primary-location invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from callbot_platform.crm.customers.serialize import serialize_location
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer, CustomerLocation
from callbot_platform.telephony.audit import write_audit


def _coord(value: float | Decimal | None, *, kind: str) -> Decimal | None:
    if value is None:
        return None
    try:
        num = Decimal(str(value))
    except Exception as exc:
        raise CrmError(f"invalid_{kind}", f"Invalid {kind}") from exc
    if kind == "latitude" and (num < -90 or num > 90):
        raise CrmError("invalid_latitude", "Latitude must be between -90 and 90")
    if kind == "longitude" and (num < -180 or num > 180):
        raise CrmError("invalid_longitude", "Longitude must be between -180 and 180")
    return num


class CustomerLocationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _get_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.tenant_id == tenant_id,
            )
        )
        if customer is None:
            raise CrmError("not_found", "Customer not found for tenant")
        return customer

    def _get_location(
        self, tenant_id: UUID, customer_id: UUID, location_id: UUID
    ) -> CustomerLocation:
        loc = self._session.scalar(
            select(CustomerLocation).where(
                CustomerLocation.id == location_id,
                CustomerLocation.tenant_id == tenant_id,
                CustomerLocation.customer_id == customer_id,
            )
        )
        if loc is None:
            raise CrmError("not_found", "Location not found for customer")
        return loc

    def list_locations(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self._get_customer(tenant_id, customer_id)
        q = select(CustomerLocation).where(
            CustomerLocation.tenant_id == tenant_id,
            CustomerLocation.customer_id == customer_id,
        )
        if not include_archived:
            q = q.where(CustomerLocation.archived_at.is_(None))
        q = q.order_by(
            CustomerLocation.is_primary.desc(),
            CustomerLocation.created_at.asc(),
        ).limit(max(1, min(limit, 200)))
        return [serialize_location(row) for row in self._session.scalars(q).all()]

    def get_location(
        self, tenant_id: UUID, customer_id: UUID, location_id: UUID
    ) -> dict[str, Any]:
        return serialize_location(
            self._get_location(tenant_id, customer_id, location_id)
        )

    def create_location(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        address_line_1: str,
        address_line_2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        access_instructions: str | None = None,
        label: str | None = None,
        is_primary: bool | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        customer = self._get_customer(tenant_id, customer_id)
        if customer.archived_at is not None:
            raise CrmError(
                "customer_archived", "Cannot add location to archived customer"
            )
        line1 = (address_line_1 or "").strip()
        if not line1:
            raise CrmError("invalid_address", "Address line 1 is required")
        if len(line1) > 255:
            raise CrmError("invalid_address", "Address line 1 is too long")

        active_count = self._session.scalar(
            select(CustomerLocation.id)
            .where(
                CustomerLocation.tenant_id == tenant_id,
                CustomerLocation.customer_id == customer_id,
                CustomerLocation.archived_at.is_(None),
            )
            .limit(1)
        )
        make_primary = (
            bool(is_primary) if is_primary is not None else active_count is None
        )

        if make_primary:
            self._clear_primary(tenant_id, customer_id)

        loc = CustomerLocation(
            tenant_id=tenant_id,
            customer_id=customer_id,
            label=(label.strip() if label else None) or None,
            address_line_1=line1,
            address_line_2=(address_line_2.strip() if address_line_2 else None) or None,
            city=(city.strip() if city else None) or None,
            state=(state.strip() if state else None) or None,
            postal_code=(postal_code.strip() if postal_code else None) or None,
            country=(country.strip().upper() if country else None) or None,
            latitude=_coord(latitude, kind="latitude"),
            longitude=_coord(longitude, kind="longitude"),
            access_instructions=(
                access_instructions.strip() if access_instructions else None
            )
            or None,
            is_primary=make_primary,
        )
        if loc.country and len(loc.country) != 2:
            raise CrmError("invalid_country", "Country must be a 2-letter ISO code")

        self._session.add(loc)
        self._session.flush()
        if make_primary:
            self._sync_customer_address(customer, loc)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_location_created",
            resource_ids={
                "customer_id": str(customer_id),
                "location_id": str(loc.id),
                "is_primary": make_primary,
            },
        )
        return serialize_location(loc)

    def update_location(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        location_id: UUID,
        *,
        actor: str = "system",
        **fields: Any,
    ) -> dict[str, Any]:
        loc = self._get_location(tenant_id, customer_id, location_id)
        if loc.archived_at is not None:
            raise CrmError("location_archived", "Cannot update archived location")
        allowed = {
            "label",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
            "latitude",
            "longitude",
            "access_instructions",
            "is_primary",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise CrmError("invalid_fields", f"Unknown fields: {sorted(unknown)}")

        if "address_line_1" in fields and fields["address_line_1"] is not None:
            line1 = str(fields["address_line_1"]).strip()
            if not line1:
                raise CrmError("invalid_address", "Address line 1 is required")
            loc.address_line_1 = line1
        for key in (
            "label",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "access_instructions",
        ):
            if key in fields:
                raw = fields[key]
                setattr(
                    loc,
                    key,
                    (
                        str(raw).strip()
                        if raw is not None and str(raw).strip()
                        else None
                    ),
                )
        if "country" in fields:
            raw = fields["country"]
            if raw is None or not str(raw).strip():
                loc.country = None
            else:
                code = str(raw).strip().upper()
                if len(code) != 2:
                    raise CrmError(
                        "invalid_country", "Country must be a 2-letter ISO code"
                    )
                loc.country = code
        if "latitude" in fields:
            loc.latitude = _coord(fields["latitude"], kind="latitude")
        if "longitude" in fields:
            loc.longitude = _coord(fields["longitude"], kind="longitude")

        became_primary = False
        if "is_primary" in fields and fields["is_primary"] is True:
            self._clear_primary(tenant_id, customer_id, except_id=loc.id)
            loc.is_primary = True
            became_primary = True
        elif "is_primary" in fields and fields["is_primary"] is False:
            loc.is_primary = False

        loc.updated_at = datetime.now(UTC)
        self._session.flush()
        customer = self._get_customer(tenant_id, customer_id)
        if loc.is_primary:
            self._sync_customer_address(customer, loc)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_location_updated",
            resource_ids={
                "customer_id": str(customer_id),
                "location_id": str(loc.id),
                "primary_changed": became_primary,
            },
        )
        return serialize_location(loc)

    def set_primary(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        location_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        return self.update_location(
            tenant_id,
            customer_id,
            location_id,
            actor=actor,
            is_primary=True,
        )

    def archive_location(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        location_id: UUID,
        *,
        actor: str = "system",
    ) -> dict[str, Any]:
        loc = self._get_location(tenant_id, customer_id, location_id)
        if loc.archived_at is not None:
            return serialize_location(loc)
        was_primary = loc.is_primary
        loc.archived_at = datetime.now(UTC)
        loc.is_primary = False
        loc.updated_at = datetime.now(UTC)
        self._session.flush()

        if was_primary:
            next_primary = self._session.scalar(
                select(CustomerLocation)
                .where(
                    CustomerLocation.tenant_id == tenant_id,
                    CustomerLocation.customer_id == customer_id,
                    CustomerLocation.archived_at.is_(None),
                )
                .order_by(CustomerLocation.created_at.asc())
                .limit(1)
            )
            customer = self._get_customer(tenant_id, customer_id)
            if next_primary is not None:
                next_primary.is_primary = True
                next_primary.updated_at = datetime.now(UTC)
                self._session.flush()
                self._sync_customer_address(customer, next_primary)
            else:
                customer.address = None
                customer.updated_at = datetime.now(UTC)

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_location_archived",
            resource_ids={
                "customer_id": str(customer_id),
                "location_id": str(loc.id),
                "was_primary": was_primary,
            },
        )
        return serialize_location(loc)

    def _clear_primary(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        except_id: UUID | None = None,
    ) -> None:
        stmt = (
            update(CustomerLocation)
            .where(
                CustomerLocation.tenant_id == tenant_id,
                CustomerLocation.customer_id == customer_id,
                CustomerLocation.archived_at.is_(None),
                CustomerLocation.is_primary.is_(True),
            )
            .values(is_primary=False, updated_at=datetime.now(UTC))
        )
        if except_id is not None:
            stmt = stmt.where(CustomerLocation.id != except_id)
        self._session.execute(stmt)
        self._session.flush()

    def _sync_customer_address(self, customer: Customer, loc: CustomerLocation) -> None:
        parts = [
            loc.address_line_1,
            loc.address_line_2,
            loc.city,
            loc.state,
            loc.postal_code,
            loc.country,
        ]
        customer.address = ", ".join(p for p in parts if p) or None
        customer.updated_at = datetime.now(UTC)

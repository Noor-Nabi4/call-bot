"""Idempotent Estimate → Job / Order conversion."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates.constants import (
    CONVERSION_TARGETS,
    ConversionTarget,
    EstimateItemType,
    EstimateStatus,
)
from callbot_platform.crm.estimates.fingerprint import estimate_convert_fingerprint
from callbot_platform.crm.estimates.serialize import (
    serialize_conversion,
    serialize_estimate,
)
from callbot_platform.crm.estimates.transitions import (
    EstimateTransitionService,
    is_expired,
)
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.orders import OrderService
from callbot_platform.db.models.estimates import Estimate, EstimateConversion
from callbot_platform.telephony.audit import write_audit


class EstimateConversionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transitions = EstimateTransitionService(session)

    def convert(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        actor: str,
        target_type: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        target = (target_type or "").strip().upper()
        if target not in CONVERSION_TARGETS:
            raise CrmError(
                "invalid_target_type",
                "target_type must be JOB or ORDER",
            )
        key = idempotency_key.strip() if idempotency_key else None
        req_hash = estimate_convert_fingerprint(
            estimate_id=estimate_id, target_type=target
        )

        if key:
            by_key = self._session.scalar(
                select(EstimateConversion).where(
                    EstimateConversion.tenant_id == tenant_id,
                    EstimateConversion.idempotency_key == key,
                )
            )
            if by_key is not None:
                if (
                    by_key.idempotency_request_hash
                    and by_key.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different conversion payload",
                    )
                estimate = self._session.scalar(
                    select(Estimate)
                    .where(
                        Estimate.id == by_key.estimate_id,
                        Estimate.tenant_id == tenant_id,
                    )
                    .options(
                        selectinload(Estimate.items),
                        selectinload(Estimate.customer),
                        selectinload(Estimate.location),
                        selectinload(Estimate.status_history),
                        selectinload(Estimate.conversions),
                    )
                )
                assert estimate is not None
                return {
                    "estimate": serialize_estimate(
                        estimate, include_history=True, include_conversions=True
                    ),
                    "conversion": serialize_conversion(by_key),
                    "already_converted": True,
                }

        estimate = self._session.scalar(
            select(Estimate)
            .where(Estimate.id == estimate_id, Estimate.tenant_id == tenant_id)
            .options(
                selectinload(Estimate.items),
                selectinload(Estimate.customer),
                selectinload(Estimate.location),
                selectinload(Estimate.status_history),
                selectinload(Estimate.conversions),
            )
            .with_for_update()
        )
        if estimate is None:
            raise CrmError("not_found", "Estimate not found for tenant")
        if estimate.archived_at is not None:
            raise CrmError("estimate_archived", "Cannot convert an archived estimate")

        existing = self._session.scalar(
            select(EstimateConversion).where(
                EstimateConversion.tenant_id == tenant_id,
                EstimateConversion.estimate_id == estimate_id,
            )
        )
        if existing is not None:
            return {
                "estimate": serialize_estimate(
                    estimate, include_history=True, include_conversions=True
                ),
                "conversion": serialize_conversion(existing),
                "already_converted": True,
            }

        if estimate.status != EstimateStatus.APPROVED.value:
            raise CrmError(
                "invalid_transition",
                "Only APPROVED estimates can be converted",
            )
        if is_expired(estimate):
            raise CrmError("estimate_expired", "Estimate is past valid_until")

        if target == ConversionTarget.JOB.value:
            target_id, target_number = self._create_job(
                tenant_id, estimate, actor=actor
            )
        else:
            target_id, target_number = self._create_order(
                tenant_id, estimate, actor=actor
            )

        conversion = EstimateConversion(
            tenant_id=tenant_id,
            estimate_id=estimate.id,
            target_type=target,
            target_id=target_id,
            target_number=target_number,
            idempotency_key=key,
            idempotency_request_hash=req_hash if key else None,
            created_by=actor,
        )
        self._session.add(conversion)
        try:
            with self._session.begin_nested():
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            winner = self._session.scalar(
                select(EstimateConversion).where(
                    EstimateConversion.tenant_id == tenant_id,
                    EstimateConversion.estimate_id == estimate_id,
                )
            )
            if winner is None:
                raise CrmError("convert_conflict", "Conversion conflict") from None
            estimate2 = self._session.scalar(
                select(Estimate)
                .where(Estimate.id == estimate_id, Estimate.tenant_id == tenant_id)
                .options(
                    selectinload(Estimate.items),
                    selectinload(Estimate.customer),
                    selectinload(Estimate.status_history),
                    selectinload(Estimate.conversions),
                )
            )
            assert estimate2 is not None
            return {
                "estimate": serialize_estimate(
                    estimate2, include_history=True, include_conversions=True
                ),
                "conversion": serialize_conversion(winner),
                "already_converted": True,
            }

        # Mark CONVERTED after successful target + conversion row.
        self._transitions.transition(
            tenant_id,
            estimate_id,
            to_status=EstimateStatus.CONVERTED.value,
            actor=actor,
            reason=f"converted_to_{target.lower()}",
            metadata={
                "event": "ESTIMATE_CONVERTED",
                "target_type": target,
                "target_id": str(target_id),
            },
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_converted",
            resource_ids={
                "estimate_id": str(estimate_id),
                "target_type": target,
                "target_id": str(target_id),
                "target_number": target_number,
            },
            idempotency_key=key,
        )
        estimate = self._session.scalar(
            select(Estimate)
            .where(Estimate.id == estimate_id, Estimate.tenant_id == tenant_id)
            .options(
                selectinload(Estimate.items),
                selectinload(Estimate.customer),
                selectinload(Estimate.location),
                selectinload(Estimate.status_history),
                selectinload(Estimate.conversions),
            )
        )
        assert estimate is not None
        return {
            "estimate": serialize_estimate(
                estimate, include_history=True, include_conversions=True
            ),
            "conversion": serialize_conversion(conversion),
            "already_converted": False,
        }

    def _create_job(
        self, tenant_id: UUID, estimate: Estimate, *, actor: str
    ) -> tuple[UUID, str]:
        service_items = [
            i
            for i in (estimate.items or [])
            if i.item_type == EstimateItemType.SERVICE.value and i.service_id
        ]
        service_id = service_items[0].service_id if service_items else None
        desc_parts = [
            f"{i.name_snapshot} x {i.quantity}" for i in (estimate.items or [])
        ]
        description = estimate.description or "; ".join(desc_parts)
        job = JobService(self._session).create(
            tenant_id,
            customer_id=estimate.customer_id,
            actor=actor,
            service_id=service_id,
            location_id=estimate.location_id,
            service_type=estimate.title or "Estimate work",
            description=description[:4000] if description else None,
            priority="MEDIUM",
        )
        return UUID(str(job["id"])), str(job["job_number"])

    def _create_order(
        self, tenant_id: UUID, estimate: Estimate, *, actor: str
    ) -> tuple[UUID, str]:
        product_items = [
            i
            for i in (estimate.items or [])
            if i.item_type == EstimateItemType.PRODUCT.value and i.product_id
        ]
        if not product_items:
            raise CrmError(
                "order_items_required",
                "ORDER conversion requires at least one PRODUCT line item",
            )
        items = []
        for i in product_items:
            qty = (
                int(i.quantity)
                if i.quantity == i.quantity.to_integral_value()
                else None
            )
            if qty is None or qty <= 0:
                # OrderService requires int quantity — reject fractional product qty.
                raise CrmError(
                    "invalid_quantity",
                    "ORDER conversion requires whole-number product quantities",
                )
            items.append(
                {
                    "product_id": i.product_id,
                    "variant_id": i.variant_id,
                    "quantity": qty,
                    "unit_price": str(i.unit_price),
                    "discount_total": str(i.discount_total),
                    "tax_total": str(i.tax_total),
                    "sort_order": i.sort_order,
                }
            )
        order = OrderService(self._session).create(
            tenant_id,
            customer_id=estimate.customer_id,
            actor=actor,
            items=items,
            currency=estimate.currency,
            notes=f"Converted from {estimate.estimate_number}",
            order_discount=str(estimate.estimate_discount),
        )
        return UUID(str(order["id"])), str(order["order_number"])

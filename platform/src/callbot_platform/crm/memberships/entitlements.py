"""Central membership entitlement resolution (Phase 20)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.memberships.constants import (
    ENTITLED_STATUSES,
    DiscountType,
    MembershipEvent,
    MembershipStatus,
)
from callbot_platform.crm.memberships.money import require_money, serialize_money
from callbot_platform.crm.memberships.serialize import (
    serialize_membership,
    serialize_plan,
)
from callbot_platform.db.models.memberships import (
    CustomerMembership,
    MembershipEntitlementUsage,
    MembershipHistory,
    MembershipPlan,
    MembershipPlanService,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_MONEY_ZERO = Decimal("0.0000")


class MembershipEntitlementService:
    """Single place for active membership / discount / included services / priority."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_membership(
        self, tenant_id: UUID, customer_id: UUID
    ) -> CustomerMembership | None:
        return self._session.scalar(
            select(CustomerMembership)
            .where(
                CustomerMembership.tenant_id == tenant_id,
                CustomerMembership.customer_id == customer_id,
                CustomerMembership.status.in_(tuple(ENTITLED_STATUSES)),
            )
            .order_by(CustomerMembership.created_at.desc())
            .limit(1)
        )

    def resolve_for_customer(
        self, tenant_id: UUID, customer_id: UUID
    ) -> dict[str, Any] | None:
        membership = self.get_active_membership(tenant_id, customer_id)
        if membership is None:
            return None
        plan = self._session.scalar(
            select(MembershipPlan)
            .where(
                MembershipPlan.id == membership.plan_id,
                MembershipPlan.tenant_id == tenant_id,
            )
            .options(selectinload(MembershipPlan.included_services))
        )
        if plan is None:
            return None
        included = self._included_remaining(tenant_id, membership, plan)
        return {
            "membership": serialize_membership(membership, plan=plan),
            "plan": serialize_plan(plan),
            "priority_scheduling": bool(plan.priority_scheduling),
            "discount_type": plan.discount_type,
            "discount_value": (
                serialize_money(plan.discount_value)
                if plan.discount_value is not None
                else None
            ),
            "included_services": included,
            "has_active_membership": membership.status == MembershipStatus.ACTIVE.value,
        }

    def apply_service_discount(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        *,
        unit_price: object,
    ) -> dict[str, Any]:
        """Server-authoritative membership discount on a service unit price."""
        base = require_money(unit_price, field="unit_price")
        membership = self.get_active_membership(tenant_id, customer_id)
        if membership is None:
            return {
                "unit_price": serialize_money(base),
                "discount_amount": serialize_money(_MONEY_ZERO),
                "final_unit_price": serialize_money(base),
                "membership_id": None,
            }
        plan = self._session.scalar(
            select(MembershipPlan).where(
                MembershipPlan.id == membership.plan_id,
                MembershipPlan.tenant_id == tenant_id,
            )
        )
        if plan is None or not plan.discount_type or plan.discount_value is None:
            return {
                "unit_price": serialize_money(base),
                "discount_amount": serialize_money(_MONEY_ZERO),
                "final_unit_price": serialize_money(base),
                "membership_id": str(membership.id),
            }

        discount = _MONEY_ZERO
        if plan.discount_type == DiscountType.PERCENTAGE.value:
            pct = plan.discount_value
            if pct > Decimal("100"):
                pct = Decimal("100")
            discount = (base * pct / Decimal("100")).quantize(Decimal("0.0001"))
        elif plan.discount_type == DiscountType.FIXED_AMOUNT.value:
            discount = min(base, plan.discount_value)

        final = base - discount
        if final < _MONEY_ZERO:
            final = _MONEY_ZERO
        return {
            "unit_price": serialize_money(base),
            "discount_amount": serialize_money(discount),
            "final_unit_price": serialize_money(final),
            "membership_id": str(membership.id),
            "discount_type": plan.discount_type,
        }

    def has_priority_scheduling(self, tenant_id: UUID, customer_id: UUID) -> bool:
        membership = self.get_active_membership(tenant_id, customer_id)
        if membership is None:
            return False
        plan = self._session.scalar(
            select(MembershipPlan).where(
                MembershipPlan.id == membership.plan_id,
                MembershipPlan.tenant_id == tenant_id,
            )
        )
        return bool(plan and plan.priority_scheduling)

    def remaining_for_service(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        service_id: UUID,
    ) -> int | None:
        """Remaining included quantity for service in current period, or None if N/A."""
        membership = self.get_active_membership(tenant_id, customer_id)
        if membership is None:
            return None
        plan_svc = self._session.scalar(
            select(MembershipPlanService).where(
                MembershipPlanService.tenant_id == tenant_id,
                MembershipPlanService.plan_id == membership.plan_id,
                MembershipPlanService.service_id == service_id,
            )
        )
        if plan_svc is None:
            return None
        used = self._used_quantity(
            tenant_id, membership.id, service_id, membership.current_period_start
        )
        return max(0, int(plan_svc.included_quantity) - used)

    def consume_entitlement(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        service_id: UUID,
        appointment_id: UUID,
        actor: str,
        quantity: int = 1,
    ) -> dict[str, Any] | None:
        """
        Atomically consume included-service entitlement for an appointment.

        Returns usage payload, or None if service is not included (caller charges normally).
        Raises if included but exhausted.
        """
        if quantity <= 0:
            raise CrmError("invalid_quantity", "Entitlement quantity must be positive")

        membership = self._session.scalars(
            select(CustomerMembership)
            .where(
                CustomerMembership.tenant_id == tenant_id,
                CustomerMembership.customer_id == customer_id,
                CustomerMembership.status.in_(tuple(ENTITLED_STATUSES)),
            )
            .with_for_update()
            .limit(1)
        ).first()
        if membership is None:
            return None

        plan_svc = self._session.scalar(
            select(MembershipPlanService).where(
                MembershipPlanService.tenant_id == tenant_id,
                MembershipPlanService.plan_id == membership.plan_id,
                MembershipPlanService.service_id == service_id,
            )
        )
        if plan_svc is None:
            return None

        used = self._used_quantity(
            tenant_id,
            membership.id,
            service_id,
            membership.current_period_start,
        )
        remaining = int(plan_svc.included_quantity) - used
        if remaining < quantity:
            raise CrmError(
                "entitlement_exhausted",
                "No remaining included-service entitlement for this period",
            )

        usage = MembershipEntitlementUsage(
            tenant_id=tenant_id,
            membership_id=membership.id,
            service_id=service_id,
            appointment_id=appointment_id,
            quantity=quantity,
            period_start=membership.current_period_start,
            consumed_at=datetime.now(UTC),
        )
        try:
            with self._session.begin_nested():
                self._session.add(usage)
                self._session.flush()
        except IntegrityError:
            existing = self._session.scalar(
                select(MembershipEntitlementUsage).where(
                    MembershipEntitlementUsage.membership_id == membership.id,
                    MembershipEntitlementUsage.appointment_id == appointment_id,
                    MembershipEntitlementUsage.service_id == service_id,
                )
            )
            if existing is not None:
                return {
                    "usage_id": str(existing.id),
                    "membership_id": str(membership.id),
                    "service_id": str(service_id),
                    "appointment_id": str(appointment_id),
                    "quantity": int(existing.quantity),
                    "idempotent": True,
                }
            raise

        self._session.add(
            MembershipHistory(
                tenant_id=tenant_id,
                membership_id=membership.id,
                customer_id=customer_id,
                event_type=MembershipEvent.ENTITLEMENT_USED.value,
                from_plan_id=membership.plan_id,
                to_plan_id=membership.plan_id,
                from_status=membership.status,
                to_status=membership.status,
                effective_at=datetime.now(UTC),
                actor_type="system",
                actor_id=actor,
                metadata_json={
                    "service_id": str(service_id),
                    "appointment_id": str(appointment_id),
                    "quantity": quantity,
                },
            )
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="membership.entitlement_used",
            resource_ids={
                "membership_id": str(membership.id),
                "customer_id": str(customer_id),
                "service_id": str(service_id),
                "appointment_id": str(appointment_id),
            },
        )
        logger.info(
            "membership.entitlement_consumed tenant_id=%s membership_id=%s "
            "service_id=%s appointment_id=%s",
            tenant_id,
            membership.id,
            service_id,
            appointment_id,
        )
        return {
            "usage_id": str(usage.id),
            "membership_id": str(membership.id),
            "service_id": str(service_id),
            "appointment_id": str(appointment_id),
            "quantity": quantity,
            "remaining": remaining - quantity,
            "idempotent": False,
        }

    def _used_quantity(
        self,
        tenant_id: UUID,
        membership_id: UUID,
        service_id: UUID,
        period_start: datetime,
    ) -> int:
        total = self._session.scalar(
            select(
                func.coalesce(func.sum(MembershipEntitlementUsage.quantity), 0)
            ).where(
                MembershipEntitlementUsage.tenant_id == tenant_id,
                MembershipEntitlementUsage.membership_id == membership_id,
                MembershipEntitlementUsage.service_id == service_id,
                MembershipEntitlementUsage.period_start == period_start,
            )
        )
        return int(total or 0)

    def _included_remaining(
        self,
        tenant_id: UUID,
        membership: CustomerMembership,
        plan: MembershipPlan,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in plan.included_services or []:
            used = self._used_quantity(
                tenant_id,
                membership.id,
                row.service_id,
                membership.current_period_start,
            )
            included = int(row.included_quantity)
            out.append(
                {
                    "service_id": str(row.service_id),
                    "included_quantity": included,
                    "used_quantity": used,
                    "remaining_quantity": max(0, included - used),
                }
            )
        return out

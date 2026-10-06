"""Order status transition policy and service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.orders.constants import (
    ORDER_STATUSES,
    VALID_TRANSITIONS,
    OrderStatus,
)
from callbot_platform.crm.orders.inventory import OrderInventoryService
from callbot_platform.crm.orders.serialize import (
    serialize_order,
    serialize_status_history,
)
from callbot_platform.db.models.orders import Order, OrderStatusHistory
from callbot_platform.telephony.audit import write_audit


def normalize_status(value: str) -> str:
    raw = (value or "").strip().upper()
    if raw not in ORDER_STATUSES:
        raise CrmError("invalid_status", f"Unknown order status: {value}")
    return raw


class OrderTransitionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._inventory = OrderInventoryService(session)

    def history(self, tenant_id: UUID, order_id: UUID) -> list[dict[str, Any]]:
        order = self._session.scalar(
            select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id)
        )
        if order is None:
            raise CrmError("not_found", "Order not found for tenant")
        rows = list(
            self._session.scalars(
                select(OrderStatusHistory)
                .where(
                    OrderStatusHistory.tenant_id == tenant_id,
                    OrderStatusHistory.order_id == order_id,
                )
                .order_by(
                    OrderStatusHistory.created_at.asc(), OrderStatusHistory.id.asc()
                )
            ).all()
        )
        return [serialize_status_history(r) for r in rows]

    def transition(
        self,
        tenant_id: UUID,
        order_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
        require_permission_hint: str | None = None,
    ) -> dict[str, Any]:
        """Transition order status with inventory side effects.

        ``require_permission_hint`` is informational for callers; RBAC is
        enforced at the route layer (cancel/refund vs generic transition).
        """
        order = self._session.scalar(
            select(Order)
            .where(Order.id == order_id, Order.tenant_id == tenant_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.customer),
            )
            .with_for_update()
        )
        if order is None:
            raise CrmError("not_found", "Order not found for tenant")
        if order.archived_at is not None:
            raise CrmError("order_archived", "Cannot transition an archived order")

        target = normalize_status(to_status)
        current = normalize_status(order.status)
        if current == target:
            return serialize_order(order, include_history=True)

        if (current, target) not in VALID_TRANSITIONS:
            raise CrmError(
                "invalid_transition",
                f"Transition from {current} to {target} is not allowed",
            )

        if (
            target == OrderStatus.CANCELLED.value
            and require_permission_hint == "refund"
        ):
            raise CrmError("invalid_transition", "Use cancel permission for CANCELLED")
        if (
            target == OrderStatus.REFUNDED.value
            and current != OrderStatus.DELIVERED.value
        ):
            raise CrmError(
                "invalid_transition",
                "REFUNDED is only allowed from DELIVERED",
            )

        # Inventory first so failures roll back status change with the session.
        self._inventory.apply_transition_side_effects(
            order, from_status=current, to_status=target, actor=actor
        )

        order.status = target
        order.updated_by = actor
        order.updated_at = datetime.now(UTC)

        history = OrderStatusHistory(
            tenant_id=tenant_id,
            order_id=order.id,
            from_status=current,
            to_status=target,
            changed_by=actor,
            reason=(reason.strip()[:500] if reason and reason.strip() else None),
            metadata_json={"from": current, "to": target},
        )
        self._session.add(history)
        self._session.flush()

        action = "order_status_changed"
        if target == OrderStatus.CANCELLED.value:
            action = "order_cancelled"
        elif target == OrderStatus.REFUNDED.value:
            action = "order_refunded"

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_ids={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "from": current,
                "to": target,
            },
            payload_summary={"reason": reason} if reason else None,
        )
        self._session.refresh(order)
        return serialize_order(order, include_history=True)

"""Order ↔ InventoryMutationService bridge (idempotent side effects)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.inventory.items import InventoryItemService
from callbot_platform.crm.inventory.locations import InventoryLocationService
from callbot_platform.crm.inventory.mutations import InventoryMutationService
from callbot_platform.crm.orders.constants import REF_TYPE_ORDER
from callbot_platform.db.models.inventory import InventoryTransaction
from callbot_platform.db.models.orders import Order, OrderItem

logger = logging.getLogger(__name__)


class OrderInventoryService:
    """Maps order lifecycle events onto InventoryMutationService.

    Semantics (see docs/ORDER_INVENTORY_INTEGRATION.md):
      CONFIRMED  → RESERVE per variant line
      PROCESSING → RELEASE reservation then SALE (consume)
      CANCELLED  → RELEASE if reserved-only; RETURN if already sold
      REFUNDED   → RETURN sold units (lifecycle state only; not a payment refund)

    Flags ``inventory_reserved`` / ``inventory_consumed`` are re-synced from the
    Inventory ledger (idempotency keys) before every mutation so retries after
    a crash cannot diverge from the ledger.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._mutations = InventoryMutationService(session)
        self._items = InventoryItemService(session)
        self._locations = InventoryLocationService(session)

    def _location_id(self, order: Order, *, actor: str) -> UUID:
        if order.fulfillment_location_id is not None:
            loc = self._locations.get_row(
                order.tenant_id,
                order.fulfillment_location_id,
                require_active=True,
            )
            return loc.id
        loc = self._locations.ensure_default(order.tenant_id, actor=actor)
        order.fulfillment_location_id = loc.id
        self._session.flush()
        return loc.id

    def _variant_lines(self, order: Order) -> list[OrderItem]:
        return [i for i in (order.items or []) if i.variant_id is not None]

    def _item_for_variant(self, tenant_id: UUID, variant_id: UUID, *, actor: str):
        return self._items.ensure_for_variant(tenant_id, variant_id, actor=actor)

    def _ledger_has(self, tenant_id: UUID, idempotency_key: str) -> bool:
        return (
            self._session.scalar(
                select(InventoryTransaction.id).where(
                    InventoryTransaction.tenant_id == tenant_id,
                    InventoryTransaction.idempotency_key == idempotency_key,
                )
            )
            is not None
        )

    def sync_flags_from_ledger(self, order: Order) -> None:
        """Re-derive reservation/consumption flags from inventory ledger keys."""
        lines = self._variant_lines(order)
        if not lines:
            return
        oid = order.id
        any_sale = any(
            self._ledger_has(order.tenant_id, f"order:{oid}:sale:{line.id}")
            for line in lines
        )
        any_return = any(
            self._ledger_has(order.tenant_id, f"order:{oid}:return:{line.id}")
            for line in lines
        )
        any_reserve = any(
            self._ledger_has(order.tenant_id, f"order:{oid}:reserve:{line.id}")
            for line in lines
        )
        any_rel_sale = any(
            self._ledger_has(
                order.tenant_id, f"order:{oid}:release-before-sale:{line.id}"
            )
            for line in lines
        )
        any_rel_cancel = any(
            self._ledger_has(order.tenant_id, f"order:{oid}:release-cancel:{line.id}")
            for line in lines
        )

        if any_sale:
            order.inventory_consumed = True
            order.inventory_reserved = False
        elif any_reserve and not any_rel_sale and not any_rel_cancel:
            order.inventory_reserved = True
            order.inventory_consumed = False
        else:
            order.inventory_reserved = False
            if any_return:
                order.inventory_consumed = True
        self._session.flush()

    def reserve_for_order(self, order: Order, *, actor: str) -> None:
        self.sync_flags_from_ledger(order)
        if order.inventory_reserved or order.inventory_consumed:
            return
        lines = self._variant_lines(order)
        if not lines:
            order.inventory_reserved = True
            self._session.flush()
            return
        location_id = self._location_id(order, actor=actor)
        for line in lines:
            assert line.variant_id is not None
            inv = self._item_for_variant(order.tenant_id, line.variant_id, actor=actor)
            self._mutations.reserve(
                order.tenant_id,
                inv.id,
                location_id=location_id,
                quantity=line.quantity,
                actor=actor,
                reason=f"Order {order.order_number} confirmed",
                reference_type=REF_TYPE_ORDER,
                reference_id=str(order.id),
                idempotency_key=f"order:{order.id}:reserve:{line.id}",
                metadata={"order_item_id": str(line.id)},
            )
        order.inventory_reserved = True
        self._session.flush()

    def consume_for_order(self, order: Order, *, actor: str) -> None:
        self.sync_flags_from_ledger(order)
        if order.inventory_consumed:
            return
        lines = self._variant_lines(order)
        if not lines:
            order.inventory_reserved = False
            order.inventory_consumed = True
            self._session.flush()
            return
        location_id = self._location_id(order, actor=actor)
        for line in lines:
            assert line.variant_id is not None
            inv = self._item_for_variant(order.tenant_id, line.variant_id, actor=actor)
            # SALE uses available = stock - reserved. Release first when reserved.
            if order.inventory_reserved or self._ledger_has(
                order.tenant_id, f"order:{order.id}:reserve:{line.id}"
            ):
                self._mutations.release(
                    order.tenant_id,
                    inv.id,
                    location_id=location_id,
                    quantity=line.quantity,
                    actor=actor,
                    reason=f"Order {order.order_number} processing (release before sale)",
                    reference_type=REF_TYPE_ORDER,
                    reference_id=str(order.id),
                    idempotency_key=f"order:{order.id}:release-before-sale:{line.id}",
                    metadata={"order_item_id": str(line.id)},
                )
            self._mutations.sale(
                order.tenant_id,
                inv.id,
                location_id=location_id,
                quantity=line.quantity,
                actor=actor,
                reason=f"Order {order.order_number} processing",
                reference_type=REF_TYPE_ORDER,
                reference_id=str(order.id),
                idempotency_key=f"order:{order.id}:sale:{line.id}",
                metadata={"order_item_id": str(line.id)},
            )
        order.inventory_reserved = False
        order.inventory_consumed = True
        self._session.flush()

    def release_reservation(self, order: Order, *, actor: str) -> None:
        self.sync_flags_from_ledger(order)
        if order.inventory_consumed:
            return
        if not order.inventory_reserved:
            return
        lines = self._variant_lines(order)
        if not lines:
            order.inventory_reserved = False
            self._session.flush()
            return
        location_id = self._location_id(order, actor=actor)
        for line in lines:
            assert line.variant_id is not None
            inv = self._item_for_variant(order.tenant_id, line.variant_id, actor=actor)
            self._mutations.release(
                order.tenant_id,
                inv.id,
                location_id=location_id,
                quantity=line.quantity,
                actor=actor,
                reason=f"Order {order.order_number} cancelled",
                reference_type=REF_TYPE_ORDER,
                reference_id=str(order.id),
                idempotency_key=f"order:{order.id}:release-cancel:{line.id}",
                metadata={"order_item_id": str(line.id)},
            )
        order.inventory_reserved = False
        self._session.flush()

    def return_consumed(self, order: Order, *, actor: str) -> None:
        self.sync_flags_from_ledger(order)
        if not order.inventory_consumed:
            return
        lines = self._variant_lines(order)
        if not lines:
            return
        location_id = self._location_id(order, actor=actor)
        for line in lines:
            assert line.variant_id is not None
            inv = self._item_for_variant(order.tenant_id, line.variant_id, actor=actor)
            self._mutations.return_stock(
                order.tenant_id,
                inv.id,
                location_id=location_id,
                quantity=line.quantity,
                actor=actor,
                reason=f"Order {order.order_number} cancelled/refunded restock",
                reference_type=REF_TYPE_ORDER,
                reference_id=str(order.id),
                idempotency_key=f"order:{order.id}:return:{line.id}",
                metadata={"order_item_id": str(line.id)},
            )
        # Keep inventory_consumed=True so we do not re-sale; return is idempotent.
        self._session.flush()

    def apply_transition_side_effects(
        self,
        order: Order,
        *,
        from_status: str,
        to_status: str,
        actor: str,
    ) -> None:
        from callbot_platform.crm.orders.constants import OrderStatus

        if to_status == OrderStatus.CONFIRMED.value:
            self.reserve_for_order(order, actor=actor)
            return
        if to_status == OrderStatus.PROCESSING.value:
            self.consume_for_order(order, actor=actor)
            return
        if to_status == OrderStatus.CANCELLED.value:
            self.sync_flags_from_ledger(order)
            if order.inventory_consumed:
                self.return_consumed(order, actor=actor)
            elif order.inventory_reserved:
                self.release_reservation(order, actor=actor)
            return
        if to_status == OrderStatus.REFUNDED.value:
            # Lifecycle only — payment refund is future Payments domain.
            self.return_consumed(order, actor=actor)
            return
        _ = from_status
        logger.debug(
            "order_inventory_noop",
            extra={
                "order_id": str(order.id),
                "from": from_status,
                "to": to_status,
            },
        )

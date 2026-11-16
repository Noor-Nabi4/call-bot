"""Atomic inventory mutations (single entry point for stock changes)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory.alerts import InventoryAlertService
from callbot_platform.crm.inventory.constants import (
    OUTBOX_RELEASED,
    OUTBOX_RESERVED,
    OUTBOX_STOCK_CHANGED,
    RESERVATION_TRANSACTION_TYPES,
    STOCK_TRANSACTION_TYPES,
    TX_ADJUSTMENT,
    TX_PURCHASE,
    TX_RELEASE,
    TX_RESERVATION,
    TX_RETURN,
    TX_SALE,
)
from callbot_platform.crm.inventory.items import InventoryItemService
from callbot_platform.crm.inventory.locations import InventoryLocationService
from callbot_platform.crm.inventory.serialize import serialize_transaction
from callbot_platform.crm.inventory.status import available_quantity, derive_status
from callbot_platform.db.models import ProductVariant
from callbot_platform.db.models.inventory import (
    InventoryBalance,
    InventoryOutboxEvent,
    InventoryTransaction,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class InventoryMutationService:
    """All stock/reservation changes flow through this service."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._items = InventoryItemService(session)
        self._locations = InventoryLocationService(session)
        self._alerts = InventoryAlertService(session)

    def purchase(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        quantity: int,
        actor: str,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            tx_type=TX_PURCHASE,
            quantity=quantity,
            actor=actor,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def sale(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        quantity: int,
        actor: str,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            tx_type=TX_SALE,
            quantity=quantity,
            actor=actor,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def adjust(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        quantity: int,
        actor: str,
        reason: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not reason or not reason.strip():
            raise CrmError("reason_required", "Adjustment requires a reason")
        return self._apply(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            tx_type=TX_ADJUSTMENT,
            quantity=quantity,
            actor=actor,
            reason=reason.strip(),
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def return_stock(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        quantity: int,
        actor: str,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            tx_type=TX_RETURN,
            quantity=quantity,
            actor=actor,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def reserve(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        quantity: int,
        actor: str,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            tx_type=TX_RESERVATION,
            quantity=quantity,
            actor=actor,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def configure_minimum(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        minimum_stock: int,
    ) -> InventoryBalance:
        if minimum_stock < 0:
            raise CrmError("invalid_minimum", "minimum_stock must be non-negative")
        self._items.get_row(tenant_id, inventory_item_id)
        self._locations.get_row(tenant_id, location_id)
        balance = self._lock_balance(tenant_id, inventory_item_id, location_id)
        balance.minimum_stock = minimum_stock
        self._session.flush()
        return balance

    def release(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        quantity: int,
        actor: str,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._apply(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            tx_type=TX_RELEASE,
            quantity=quantity,
            actor=actor,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def _apply(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        tx_type: str,
        quantity: int,
        actor: str,
        reason: str | None,
        reference_type: str | None,
        reference_id: str | None,
        idempotency_key: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        if key:
            existing = self._session.scalar(
                select(InventoryTransaction).where(
                    InventoryTransaction.tenant_id == tenant_id,
                    InventoryTransaction.idempotency_key == key,
                )
            )
            if existing is not None:
                return {
                    "transaction": serialize_transaction(existing),
                    "idempotent": True,
                }

        item = self._items.get_row(tenant_id, inventory_item_id)
        self._locations.get_row(tenant_id, location_id, require_active=True)

        if tx_type == TX_ADJUSTMENT:
            if quantity == 0:
                raise CrmError("invalid_quantity", "Adjustment quantity cannot be zero")
        elif quantity <= 0:
            raise CrmError("invalid_quantity", "Quantity must be positive")

        balance = self._lock_balance(tenant_id, inventory_item_id, location_id)
        stock_before = balance.stock_quantity
        reserved_before = balance.reserved_quantity
        avail_before = available_quantity(stock_before, reserved_before)

        stock_after, reserved_after = self._compute_new(
            tx_type,
            stock_before,
            reserved_before,
            quantity,
            avail_before,
        )

        tx = InventoryTransaction(
            tenant_id=tenant_id,
            inventory_item_id=inventory_item_id,
            location_id=location_id,
            transaction_type=tx_type,
            quantity=quantity,
            stock_before=stock_before,
            stock_after=stock_after,
            reserved_before=reserved_before,
            reserved_after=reserved_after,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=key,
            reason=reason,
            metadata_json=metadata or {},
            created_by=actor,
        )
        self._session.add(tx)

        balance.stock_quantity = stock_after
        balance.reserved_quantity = reserved_after
        balance.version += 1
        self._session.flush()

        self._sync_variant_stock(tenant_id, item.variant_id)
        self._emit_transaction_outbox(
            tenant_id,
            tx,
            balance,
            idempotency_suffix=key,
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action=f"inventory.{tx_type.lower()}",
            resource_ids={
                "inventory_item_id": str(inventory_item_id),
                "location_id": str(location_id),
                "transaction_id": str(tx.id),
            },
            idempotency_key=key,
            payload_summary={
                "quantity": quantity,
                "stock_before": stock_before,
                "stock_after": stock_after,
                "reserved_before": reserved_before,
                "reserved_after": reserved_after,
                "reference_type": reference_type,
                "reference_id": reference_id,
            },
        )
        self._alerts.after_balance_change(
            tenant_id,
            item=item,
            balance=balance,
            actor=actor,
            transaction_id=tx.id,
        )

        logger.info(
            "inventory_transaction",
            extra={
                "tenant_id": str(tenant_id),
                "inventory_item_id": str(inventory_item_id),
                "location_id": str(location_id),
                "transaction_type": tx_type,
                "result": "success",
            },
        )
        return {"transaction": serialize_transaction(tx), "idempotent": False}

    def _compute_new(
        self,
        tx_type: str,
        stock: int,
        reserved: int,
        quantity: int,
        avail: int,
    ) -> tuple[int, int]:
        if tx_type in STOCK_TRANSACTION_TYPES:
            if tx_type == TX_SALE:
                if quantity > avail:
                    raise CrmError(
                        "insufficient_stock",
                        "Sale quantity exceeds available stock",
                    )
                return stock - quantity, reserved
            if tx_type == TX_PURCHASE:
                return stock + quantity, reserved
            if tx_type == TX_RETURN:
                return stock + quantity, reserved
            if tx_type == TX_ADJUSTMENT:
                new_stock = stock + quantity
                if new_stock < 0:
                    raise CrmError(
                        "insufficient_stock",
                        "Adjustment would result in negative stock",
                    )
                if new_stock < reserved:
                    raise CrmError(
                        "invalid_adjustment",
                        "Adjustment would leave reserved quantity greater than stock",
                    )
                return new_stock, reserved
        if tx_type in RESERVATION_TRANSACTION_TYPES:
            if tx_type == TX_RESERVATION:
                if quantity > avail:
                    raise CrmError(
                        "insufficient_available",
                        "Reservation exceeds available quantity",
                    )
                return stock, reserved + quantity
            if tx_type == TX_RELEASE:
                if quantity > reserved:
                    raise CrmError(
                        "insufficient_reserved",
                        "Release exceeds reserved quantity",
                    )
                return stock, reserved - quantity
        raise CrmError("invalid_transaction_type", "Unknown transaction type")

    def _lock_balance(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        location_id: UUID,
    ) -> InventoryBalance:
        row = self._session.scalar(
            select(InventoryBalance)
            .where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.inventory_item_id == inventory_item_id,
                InventoryBalance.location_id == location_id,
            )
            .with_for_update()
        )
        if row is not None:
            return row
        row = InventoryBalance(
            tenant_id=tenant_id,
            inventory_item_id=inventory_item_id,
            location_id=location_id,
            stock_quantity=0,
            reserved_quantity=0,
            minimum_stock=0,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.expire(row)
            row = self._session.scalar(
                select(InventoryBalance)
                .where(
                    InventoryBalance.tenant_id == tenant_id,
                    InventoryBalance.inventory_item_id == inventory_item_id,
                    InventoryBalance.location_id == location_id,
                )
                .with_for_update()
            )
            if row is None:
                raise CrmError(
                    "balance_unavailable", "Could not lock inventory balance"
                ) from None
            return row
        locked = self._session.scalar(
            select(InventoryBalance)
            .where(InventoryBalance.id == row.id)
            .with_for_update()
        )
        if locked is None:
            raise CrmError("balance_unavailable", "Could not lock inventory balance")
        return locked

    def _sync_variant_stock(self, tenant_id: UUID, variant_id: UUID) -> None:
        item_id = self._items.get_by_variant(tenant_id, variant_id)
        if item_id is None:
            return
        total = self._session.scalar(
            select(func.coalesce(func.sum(InventoryBalance.stock_quantity), 0)).where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.inventory_item_id == item_id.id,
            )
        )
        variant = self._session.scalar(
            select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.id == variant_id,
            )
        )
        if variant is not None:
            variant.stock_on_hand = int(total or 0)

    def _emit_transaction_outbox(
        self,
        tenant_id: UUID,
        tx: InventoryTransaction,
        balance: InventoryBalance,
        *,
        idempotency_suffix: str | None,
    ) -> None:
        """Emit durable stock-movement events (alerts emit separate outbox rows)."""
        avail = available_quantity(balance.stock_quantity, balance.reserved_quantity)
        status = derive_status(
            stock=balance.stock_quantity,
            reserved=balance.reserved_quantity,
            minimum_stock=balance.minimum_stock,
        )
        if tx.transaction_type == TX_RESERVATION:
            event_type = OUTBOX_RESERVED
        elif tx.transaction_type == TX_RELEASE:
            event_type = OUTBOX_RELEASED
        else:
            event_type = OUTBOX_STOCK_CHANGED

        idem = f"tx-outbox:{tx.id}"
        if idempotency_suffix:
            idem = f"tx-outbox:{idempotency_suffix}"

        self._session.add(
            InventoryOutboxEvent(
                tenant_id=tenant_id,
                event_type=event_type,
                payload={
                    "transaction_id": str(tx.id),
                    "inventory_item_id": str(tx.inventory_item_id),
                    "location_id": str(tx.location_id),
                    "transaction_type": tx.transaction_type,
                    "available_quantity": avail,
                    "status": status,
                },
                idempotency_key=idem,
            )
        )

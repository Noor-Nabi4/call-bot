"""Low-stock detection and alert history."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.inventory.constants import (
    ALERT_LOW_STOCK,
    ALERT_OUT_OF_STOCK,
    ALERT_RECOVERED,
    OUTBOX_LOW_STOCK,
    OUTBOX_OUT_OF_STOCK,
    STATUS_IN_STOCK,
    STATUS_LOW_STOCK,
    STATUS_OUT_OF_STOCK,
)
from callbot_platform.crm.inventory.status import available_quantity, derive_status
from callbot_platform.db.models.inventory import (
    InventoryAlertConfiguration,
    InventoryAlertEvent,
    InventoryBalance,
    InventoryItem,
    InventoryOutboxEvent,
)


class InventoryAlertService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def after_balance_change(
        self,
        tenant_id: UUID,
        *,
        item: InventoryItem,
        balance: InventoryBalance,
        actor: str,
        transaction_id: UUID | None = None,
    ) -> None:
        _ = actor
        prev = balance.last_alert_status
        current = derive_status(
            stock=balance.stock_quantity,
            reserved=balance.reserved_quantity,
            minimum_stock=balance.minimum_stock,
        )
        if prev == current:
            return

        alert_type = self._alert_type_for_transition(prev, current)
        if alert_type is None:
            balance.last_alert_status = current
            return

        config = self._ensure_config(tenant_id, item.id, balance.location_id)
        if not config.enabled:
            balance.last_alert_status = current
            return

        avail = available_quantity(balance.stock_quantity, balance.reserved_quantity)
        email_status = "pending" if config.email_enabled else "skipped"
        sms_status = "pending_integration" if config.sms_enabled else "skipped"
        event = InventoryAlertEvent(
            tenant_id=tenant_id,
            inventory_item_id=item.id,
            location_id=balance.location_id,
            alert_type=alert_type,
            previous_status=prev,
            current_status=current,
            available_quantity=avail,
            minimum_stock=balance.minimum_stock,
            email_notification_status=email_status,
            sms_notification_status=sms_status,
        )
        self._session.add(event)
        self._session.flush()

        if alert_type in {ALERT_LOW_STOCK, ALERT_OUT_OF_STOCK} and config.email_enabled:
            outbox_type = (
                OUTBOX_OUT_OF_STOCK
                if alert_type == ALERT_OUT_OF_STOCK
                else OUTBOX_LOW_STOCK
            )
            self._session.add(
                InventoryOutboxEvent(
                    tenant_id=tenant_id,
                    event_type=outbox_type,
                    payload={
                        "alert_event_id": str(event.id),
                        "inventory_item_id": str(item.id),
                        "location_id": str(balance.location_id),
                        "available_quantity": avail,
                        "minimum_stock": balance.minimum_stock,
                        "status": current,
                        "transaction_id": str(transaction_id) if transaction_id else None,
                    },
                    idempotency_key=f"alert-outbox:{event.id}",
                )
            )
            self._session.flush()

        balance.last_alert_status = current

    def _ensure_config(
        self, tenant_id: UUID, item_id: UUID, location_id: UUID
    ) -> InventoryAlertConfiguration:
        row = self._session.scalar(
            select(InventoryAlertConfiguration).where(
                InventoryAlertConfiguration.tenant_id == tenant_id,
                InventoryAlertConfiguration.inventory_item_id == item_id,
                InventoryAlertConfiguration.location_id == location_id,
            )
        )
        if row is not None:
            return row
        row = InventoryAlertConfiguration(
            tenant_id=tenant_id,
            inventory_item_id=item_id,
            location_id=location_id,
        )
        self._session.add(row)
        self._session.flush()
        return row

    @staticmethod
    def _alert_type_for_transition(prev: str | None, current: str) -> str | None:
        if current == STATUS_LOW_STOCK and prev != STATUS_LOW_STOCK:
            return ALERT_LOW_STOCK
        if current == STATUS_OUT_OF_STOCK and prev != STATUS_OUT_OF_STOCK:
            return ALERT_OUT_OF_STOCK
        if current == STATUS_IN_STOCK and prev in {
            STATUS_LOW_STOCK,
            STATUS_OUT_OF_STOCK,
        }:
            return ALERT_RECOVERED
        return None

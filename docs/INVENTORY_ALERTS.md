# Inventory alerts

Threshold: `inventory_balances.minimum_stock`.

Status is derived: `OUT_OF_STOCK` (available ≤ 0), `LOW_STOCK` (0 < available ≤ minimum), else `IN_STOCK`.

## Lifecycle

```text
Mutation TX
  → derive status
  → if transition + config enabled: inventory_alert_events row
  → emit inventory_outbox_events (INVENTORY_LOW_STOCK / OUT_OF_STOCK)
COMMIT
  → InventoryOutboxWorker
  → NotificationService.enqueue_email → notification_outbox
  → NotificationOutboxWorker → provider
```

Dedup: `inventory_balances.last_alert_status` — repeated mutations while status is unchanged do not re-alert.

Email: tenant profile email when `inventory_alert_configurations.email_enabled` (default on). Worker enqueue uses idempotency key `inventory-alert:{alert_event_id}:email`.

SMS: boundary only (`sms_enabled` → `pending_integration`).

## Outbox worker

`InventoryOutboxWorker` uses the same settings as notification outbox (`OUTBOX_*`): batch size, lease, max retries, exponential backoff. Terminal failure status: `dead_letter` with `error` retained for diagnosis.

Processed events are not reclaimed. Retry after partial success is idempotent (alert `email_notification_status` + notification outbox key).

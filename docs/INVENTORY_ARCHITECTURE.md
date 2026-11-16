# Inventory architecture (Phase 6)

Authoritative stock lives in **inventory balances** (`inventory_balances.stock_quantity` / `reserved_quantity`), not in `product_variants.stock_on_hand`.

## Model

```text
Product
   ↓
Variant  →  (auto-provisions Inventory Item on create)
   ↓
Inventory Item
   ↓
Location
   ↓
Inventory Balance
   ↓
Inventory Transaction
   ↓
Audit + inventory_outbox_events
   ↓
InventoryOutboxWorker → notification_outbox → email/SMS workers
```

`product_variants.stock_on_hand` is a **transitional compatibility field** (sum of stock across locations after mutations). It must never be treated as the source of truth. Safe removal requires migrating all readers first; do not drop blindly.

## Concurrency (PostgreSQL locking)

Mutation sequence (authoritative):

```text
BEGIN
  SELECT inventory_balance FOR UPDATE
  Reload / validate
  INSERT inventory_transaction
  UPDATE inventory_balance
  Sync transitional stock_on_hand
  INSERT inventory_outbox_events (stock movement)
  write_audit
  Alert evaluation → may INSERT alert outbox
COMMIT
```

Database row locking is the correctness mechanism. Do not replace with Redis application locks.

PostgreSQL parallel contention tests live in `tests/test_inventory_pg_concurrency.py` (`INVENTORY_PG_TEST_URL`).

## Auto-provisioning

Creating a product variant calls `InventoryItemService.ensure_for_variant` in the same transaction. Idempotent; unique `(tenant_id, variant_id)`. Balances are still created lazily on first stock mutation at a location.

Backfill existing variants: `uv run python scripts/backfill_inventory_items.py` (reports `variants_without_inventory_item_before`, `created`, `already_existing`, `failed`).

## Events / outbox

- Stock movement events: `INVENTORY_STOCK_CHANGED`, `INVENTORY_RESERVED`, `INVENTORY_RELEASED`
- Alert transition events: `INVENTORY_LOW_STOCK`, `INVENTORY_OUT_OF_STOCK` (from alert service)
- Worker: `InventoryOutboxWorker` (same process as `python -m callbot_platform.workers.run_outbox`)
- Claim: `FOR UPDATE SKIP LOCKED` on PostgreSQL; retry/backoff/dead_letter aligned with notification outbox settings
- Low-stock email is enqueued to `notification_outbox` by the inventory worker (never synchronously in the mutation TX)

## Low-stock UI filter

Dashboard links use `/crm/inventory?low_stock=true` and `?out_of_stock=true`. The CRM inventory page reads those query params and passes them to the API (server-side filter).

## Production verification status

```text
Local SQLite tests: executed
PostgreSQL concurrency: executed when INVENTORY_PG_TEST_URL / local test DB available
Staging migration / load / email provider: NOT EXECUTED
Production readiness: BLOCKED
```

## Future integration

Orders, jobs, and fulfillment should call `InventoryService` mutation/reservation methods with idempotency keys — not SQL or direct balance updates.

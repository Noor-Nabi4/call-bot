# Inventory transactions

Every stock change creates an `inventory_transactions` row. Balances are never patched directly via API.

| Type        | Stock | Reserved |
| ----------- | ----: | -------: |
| PURCHASE    |     + |        0 |
| SALE        |     - |        0 |
| ADJUSTMENT  |   +/- |        0 |
| RETURN      |     + |        0 |
| RESERVATION |     0 |        + |
| RELEASE     |     0 |        - |

## Concurrency guarantees

Under PostgreSQL `FOR UPDATE` serialization:

- Concurrent sales of overlapping available qty: at most one succeeds
- Concurrent reservations of overlapping available qty: at most one succeeds
- Concurrent sale + reservation: exactly one consumes the contested available qty
- Concurrent releases of overlapping reserved qty: at most one succeeds

Invariants always hold:

```text
stock_quantity >= 0
reserved_quantity >= 0
reserved_quantity <= stock_quantity
available_quantity = stock_quantity - reserved_quantity >= 0
```

## Idempotency

`tenant_id` + `Idempotency-Key` header (unique when present). Retries return the original transaction.

Adjustment requires `reason`.

## Migrations

- `0032_inventory` — domain tables; backfills positive `stock_on_hand` into `PRIMARY` with an `ADJUSTMENT` ledger row
- `0033_inventory_outbox_worker` — claim/retry columns on `inventory_outbox_events`

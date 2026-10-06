# Order ↔ Inventory Integration (Phase 9)

Inventory remains authoritative. Orders never `UPDATE` stock balances directly.

All mutations go through `InventoryMutationService` with idempotency keys:

```text
order:{order_id}:reserve:{order_item_id}
order:{order_id}:release-before-sale:{order_item_id}
order:{order_id}:sale:{order_item_id}
order:{order_id}:release-cancel:{order_item_id}
order:{order_id}:return:{order_item_id}
```

## Mapping

| Transition | Inventory effect |
|------------|------------------|
| → CONFIRMED | `RESERVE` per variant line |
| → PROCESSING | `RELEASE` reservation then `SALE` (consume) |
| → CANCELLED (reserved, not sold) | `RELEASE` |
| → CANCELLED (already sold) | `RETURN` |
| → REFUNDED | `RETURN` sold units (lifecycle only) |
| → SHIPPED / DELIVERED | No inventory mutation |

Flags `inventory_reserved` / `inventory_consumed` are **re-synced from the Inventory ledger** (idempotency keys) before every mutation. Retries after a crash cannot diverge flags from the ledger.

## Why RELEASE then SALE

`InventoryMutationService.sale` deducts from **available** (`stock − reserved`). Consuming a reservation therefore requires releasing the reservation before sale so available quantity includes the reserved units.

## Scope

- Lines without `variant_id` skip inventory mutations
- Default fulfillment location is used when `fulfillment_location_id` is unset
- No warehouse WMS, carriers, or packing workflows in this phase

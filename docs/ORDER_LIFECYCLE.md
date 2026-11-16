# Order Lifecycle (Phase 9)

## Status graph

```text
DRAFT → PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED
  │         │          │            │           │
  └─────────┴──────────┴────────────┴───────────┴──→ CANCELLED

DELIVERED → REFUNDED
```

Authoritative transitions are enforced in `OrderTransitionService` (`VALID_TRANSITIONS`). Invalid transitions raise `invalid_transition` and do **not** write history.

## Semantics

| Status | Meaning |
|--------|---------|
| DRAFT | Editable draft |
| PENDING | Submitted; still editable |
| CONFIRMED | Commitment; inventory reserved |
| PROCESSING | Fulfillment started; inventory sold |
| SHIPPED | Lifecycle only (no carrier/tracking) |
| DELIVERED | Lifecycle only |
| CANCELLED | Terminal cancel from eligible states |
| REFUNDED | Lifecycle mark after DELIVERED — **not** a payment refund |

## History

`order_status_history` is append-only. Creation writes `from_status=NULL → DRAFT`. Rejected transitions write nothing.

## Concurrency

Transitions load the order with `SELECT … FOR UPDATE`. Concurrent conflicting transitions: one succeeds, the other gets `invalid_transition`.

## Refund note

```text
REFUNDED = order lifecycle state
Actual payment refund processing = future Payments domain
```

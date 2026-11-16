# Orders (Phase 9)

First-class relational Order domain. Connects Customer → Order → Order Items → Product/Variant → Inventory.

Orders are **not** Dynamic CRM EAV / custom objects. Dynamic CRM may expose `ORDERS` as `PLATFORM_ENTITY` for navigation/custom fields only.

## Schema

### `orders`

| Field | Notes |
|-------|--------|
| `id`, `tenant_id` | Tenant-scoped PK |
| `order_number` | Human-readable `ORD-######`, tenant-unique, concurrency-safe |
| `customer_id` | **Required** FK → `customers` (RESTRICT) |
| `status` | Lifecycle status (see ORDER_LIFECYCLE.md) |
| `currency` | Explicit ISO-4217-style code (`USD`, `CAD`, `EUR`, `GBP`, `AUD`) |
| `subtotal`, `discount_total`, `tax_total`, `shipping_total`, `total` | `NUMERIC(19,4)` Decimal money |
| `notes` | Optional |
| `shipping_address_snapshot`, `billing_address_snapshot` | JSON snapshots (no carrier integration) |
| `fulfillment_location_id` | Optional inventory location for reserve/sale |
| `inventory_reserved`, `inventory_consumed` | Idempotency flags for inventory side effects |
| `idempotency_key` | Tenant-unique create idempotency |
| `archived_at` | Soft archive |

### `order_items`

Historical transaction snapshots: `sku_snapshot`, `product_name_snapshot`, `variant_name_snapshot`, `unit_price`, `quantity`, discounts/tax/line totals.

Product/Variant FKs remain for lineage; display/totals use snapshots.

### `order_status_history`

Append-only status events (`from_status`, `to_status`, `changed_by`, `reason`, `metadata`).

### `order_number_counters`

Per-tenant monotonic sequence (`FOR UPDATE`).

## Money

All money fields use Decimal / NUMERIC. Never float.

Totals (server-side):

```text
line_subtotal = unit_price × quantity
line_total    = line_subtotal − line_discount + line_tax
subtotal      = Σ line_subtotal
discount_total= Σ line_discount + order_discount
tax_total     = Σ line_tax
total         = subtotal − discount_total + tax_total + shipping_total
```

Tax uses the product `tax_rate` percent at creation time (not a jurisdiction engine). Historical tax is never recalculated from today's catalog.

## Price resolution

Catalog price at create time: variant.price if set, else product.price. Stored as `unit_price` snapshot. Catalog price changes do not rewrite historical lines.

## Idempotency

Create supports `Idempotency-Key` (header or body).

- Same key + same material payload → original Order
- Same key + different payload → `idempotency_conflict` (409)
- Concurrent same-key creates → one Order (DB unique + savepoint)

Fingerprint stored as `idempotency_request_hash` (migration `0038_orders_hardening`).

## Mutation rules

| Status | Line items / money editable? |
|--------|------------------------------|
| DRAFT, PENDING | Yes |
| CONFIRMED+ | No (use transition API for status only) |

Status cannot be set via `PATCH` — use `POST …/transition`, `/cancel`, or `/refund`.

## APIs

Admin base: `/api/admin/crm/orders`

- `GET/POST /orders` (`Idempotency-Key` header supported)
- `GET/PATCH/DELETE /orders/{id}` (DELETE = archive)
- `POST /orders/{id}/restore`
- `POST /orders/{id}/transition`
- `POST /orders/{id}/cancel`
- `POST /orders/{id}/refund` — **lifecycle only**; payment refund is future Payments domain
- `GET /orders/{id}/history`

Search filters (DB-side): order number, customer, status, date range, product, SKU. Keyset cursor pagination (max 200).

## RBAC

`orders.read|create|update|delete|transition|cancel|refund`

AI Agent: `orders.read`, `orders.create` only — **not** delete/cancel/refund/transition.

## Tenant isolation

All queries filter `tenant_id` from the authenticated session. Cross-tenant customer/product/variant refs fail closed.

## Related docs

- [ORDER_LIFECYCLE.md](./ORDER_LIFECYCLE.md)
- [ORDER_INVENTORY_INTEGRATION.md](./ORDER_INVENTORY_INTEGRATION.md)

## Known limitations

- No Payments, Invoices, Checkout, Cart, Shipping carriers, Refund provider APIs
- `REFUNDED` is an Order lifecycle state only
- Guest orders not supported (`customer_id` required)
- Minimal tax (product tax_rate percent)

## Staging status

```text
LOCAL: VERIFIED (Phase 9 + 9.x hardening; see prior Orders hardening report)
STAGING MIGRATION: NOT AVAILABLE — no staging DATABASE_URL / APP_ENV=staging
STAGING RBAC RECONCILE: NOT EXECUTED — blocked on staging
STAGING SMOKE: NOT EXECUTED — blocked on staging
PRODUCTION: NOT EXECUTED — .env.production is ENVIRONMENT=production; intentionally not touched
```

Blockers before STAGING VERIFIED:

1. Provide a labeled staging database + API (not production Supabase)
2. Commit/deploy migrations `0037_orders` + `0038_orders_hardening` (currently untracked in git)
3. Run `alembic upgrade head` on staging only
4. Reconcile RBAC (`POST /api/admin/organization/reconcile` or `reconcile_system_roles_for_tenant`)
5. Execute Orders smoke + negative matrix on staging

Production readiness remains **BLOCKED** until staging verification completes.

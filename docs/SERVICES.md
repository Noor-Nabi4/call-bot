# Services

First-class relational service catalog (Phase 7). Not Dynamic CRM EAV.

## Schema

`services` — tenant-scoped offerings:

| Column | Notes |
|--------|--------|
| `tenant_id` | Required; server-derived |
| `name` | Required |
| `code` / `code_normalized` | Optional; unique among active rows per tenant |
| `category_id` | FK → `service_categories` |
| `duration_minutes` | Positive when set |
| `base_price` / `cost` | `NUMERIC(19,4)`; never float |
| `tax_rate` | Percent 0–100 (not a tax engine) |
| `pricing_type` | `FIXED` \| `STARTING_AT` \| `HOURLY` \| `CUSTOM_QUOTE` |
| `status` | `ACTIVE` \| `INACTIVE` |
| `archived_at` | Soft archive |

## APIs

Prefix: `/api/admin/crm`

- `GET/POST /services`
- `GET/PATCH/DELETE /services/{id}`
- `POST /services/{id}/restore`
- `GET /services/{id}/pricing` — authoritative resolver (see PRICEBOOK_PRICING.md)

List supports cursor pagination (max 200), search (`q`), category/status filters, price/duration bounds. Archived rows excluded by default.

## RBAC

- `services.read` / `create` / `update` / `delete`
- AI Agent: `services.read` only (plus pricebook read for resolution)

## Tenant isolation

All queries filter `tenant_id` from authenticated session. Cross-tenant id access returns `not_found`.

## Dynamic CRM

Module `SERVICES` is `PLATFORM_ENTITY`. Records live in `services`, not custom objects.

## Staging verification

**STATUS = NOT EXECUTED** — local DB-backed tests + PostgreSQL concurrency tests where available. Production readiness remains **BLOCKED** until staging verification runs.

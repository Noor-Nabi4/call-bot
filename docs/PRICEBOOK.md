# Pricebook

Tenant pricebooks for service pricing, labor, and material composition (Phase 7).

## Schema

- `pricebooks` — name, status, `is_default`, effective range, soft archive
- `pricebook_items` — service + pricing type + amounts + effective range
- `pricebook_item_components` — `LABOR` | `MATERIAL` (materials → `product_variants`)
- `pricebook_overrides` — tenant/org overrides (platform is tenant-per-organization)

## Rules

- Multiple pricebooks per tenant; at most one active default
- Items/components/overrides must share the pricebook’s `tenant_id`
- Material components must reference a same-tenant product variant
- Non-overlapping active effective ranges for the same pricebook + service
  - App-layer: `FOR UPDATE` + overlap check
  - PostgreSQL: exclusion constraints (`0035_services_pricebook_hardening`)
- Inclusive `[effective_from, effective_until]` (see PRICEBOOK_PRICING.md)
- Inventory is **not** mutated from this domain

## Hardening migration

`0035_services_pricebook_hardening` (after `0034_services_pricebook`) adds PG-only
`btree_gist` exclusion constraints for active item/override ranges. SQLite skips
those DDL statements; application locking still applies.

## APIs

- `GET/POST /api/admin/crm/pricebooks`
- `GET/PATCH/DELETE /api/admin/crm/pricebooks/{id}`
- `POST /api/admin/crm/pricebooks/{id}/restore`
- `GET/POST /api/admin/crm/pricebooks/{id}/items`
- `PATCH/DELETE /api/admin/crm/pricebooks/{id}/items/{itemId}`
- `POST/DELETE .../overrides`

## RBAC

- `pricebooks.*`
- `pricebook_items.*`
- AI Agent: read-only pricebooks / pricebook_items

## Future

Jobs / invoices / appointments consume resolved prices; they are out of scope for Phase 7.

## Staging verification

**STATUS = NOT EXECUTED**

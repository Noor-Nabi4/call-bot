# Equipment / Assets (Phase 21)

Tenant-scoped installed assets linked to customers and customer locations. Service history is **derived** from jobs, job notes, orders/invoices, and equipment attachments — not duplicated in a separate ledger.

## Model

- Table: `equipment` (migration `0049_equipment`)
- Optional `jobs.equipment_id` FK (one asset per job)
- `equipment_attachments` for photos (object storage keys, tenant-prefixed)

Serial numbers: trimmed display value + uppercase normalized key; unique per tenant when present (`uq_equipment_tenant_serial_norm` partial index on PostgreSQL). Application also pre-checks duplicates for SQLite tests.

## Status lifecycle

`ACTIVE` | `INACTIVE` | `RETIRED` | `REMOVED`. Prefer status changes over hard delete when jobs reference equipment.

## Warranty

Server-derived only: `UNKNOWN`, `NOT_ACTIVE`, `ACTIVE`, `EXPIRED` via `EquipmentWarrantyService`. Clients must not set “warranty active” directly.

## APIs

Prefix: `/api/admin/crm`

| Method | Path |
|--------|------|
| GET | `/equipment` |
| POST | `/equipment` |
| GET | `/equipment/{id}` |
| PATCH | `/equipment/{id}` |
| DELETE | `/equipment/{id}` |
| GET | `/equipment/{id}/history` |
| GET/POST/DELETE | `/equipment/{id}/attachments` |

Permissions: `equipment.read`, `equipment.create`, `equipment.update`, `equipment.delete`. History uses `equipment.read`.

## Job integration

Create/update job with optional `equipment_id`. Validates tenant, customer, location (when both set), and selectable equipment status.

## Frontend

- `/crm/equipment` list and detail
- `/crm/equipment/new?customer_id=…`
- Customer profile equipment section
- Job detail equipment selector

## Verification

- Local: `uv run pytest tests/test_equipment_crm.py`
- PostgreSQL concurrency: `uv run pytest tests/test_equipment_pg_concurrency.py`
  - Same-tenant duplicate serial under concurrency → one success, others `serial_conflict`
  - Cross-tenant same serial → both succeed
  - Partial unique index `uq_equipment_tenant_serial_norm` present
- Migration `0049_equipment`: local PostgreSQL upgrade/downgrade from stamped `0048_memberships` VERIFIED
- Performance EXPLAIN / large datasets: NOT EXECUTED
- Staging / production: NOT EXECUTED

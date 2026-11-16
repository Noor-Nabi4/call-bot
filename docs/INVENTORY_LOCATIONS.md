# Inventory locations

Tenant-scoped sites: warehouse, store, office, vehicle, field, or other (`location_type` enum).

- Unique `code` per tenant (normalized).
- One `is_default` location per tenant (typically `PRIMARY`).
- Soft archive via `archived_at`; cannot archive while stock or reservations remain.

API prefix: `/api/admin/crm/inventory/locations`.

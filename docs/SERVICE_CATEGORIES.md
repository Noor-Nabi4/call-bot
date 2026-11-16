# Service Categories

Nested service taxonomy (Phase 7). Separate from product categories.

## Schema

`service_categories` — `tenant_id`, `name`, `slug`, `parent_id`, `sort_order`, `status`, `archived_at`.

## Rules

- Parent must belong to the same tenant and not be archived
- Self-parent and cycles rejected (`invalid_parent` / `category_cycle`)
- Archive blocked while active children exist
- Active services must be reassigned (or cleared) before archive when `reassign_services` is required
- Tree endpoint loads all non-archived categories once (no N+1)

## APIs

- `GET /api/admin/crm/service-categories`
- `GET /api/admin/crm/service-categories/tree`
- `POST /api/admin/crm/service-categories`
- `GET/PATCH/DELETE /api/admin/crm/service-categories/{id}`
- `POST /api/admin/crm/service-categories/{id}/restore`

## RBAC

`service_categories.read|create|update|delete`

## Staging verification

**STATUS = NOT EXECUTED**

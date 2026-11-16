# Product Categories

Nested, tenant-scoped categories for the Product Catalog.

## Model

`product_categories`: name, slug (unique per tenant), description, `parent_id`, status, sort_order, `archived_at`.

## Hierarchy rules

- Parent must same tenant and not create cycles (bounded walk, depth ≤ 20)
- Self-parent rejected
- Archive blocked when active children exist
- Archive with active products requires `reassign_products=true` (optional target category)

## APIs

```text
GET/POST  /api/admin/crm/categories
GET       /api/admin/crm/categories/tree
GET/PATCH/DELETE /api/admin/crm/categories/{id}
POST      /api/admin/crm/categories/{id}/restore
```

Tree is built from one tenant query (no N+1).

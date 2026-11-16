# Customer Search

Server-side, tenant-scoped customer search for staff and future AI tools.

> Implemented under the Phase 4 **implementation-gate override**. Staging-scale validation is **NOT EXECUTED**.

## Endpoint

```http
GET /api/admin/crm/customers?q=...
GET /api/admin/crm/customers/search?q=...
```

Also supports `status`, `include_archived`, `limit` (1–200), `cursor` (keyset).

## Matching

| Signal | Strategy |
|---|---|
| Phone | `normalize_e164` exact on `customer_phones.e164`; digit-suffix fallback for national-format input |
| Email | `email_normalized` exact (trim + lower) |
| Name | Exact → prefix → contains on `name` / `first_name` / `last_name` |
| Address | DB-side `ILIKE` on location fields + legacy `customers.address` |

## Ranking (deterministic)

1. Exact phone  
2. Exact email  
3. Exact name  
4. Prefix name  
5. Fuzzy / contains name  
6. Address  

Within a rank: `updated_at DESC`, then `id`.

## Indexes

- `customers(tenant_id, email_normalized)`
- `customers(tenant_id, name)` / optional `pg_trgm` on `name` (Postgres)
- `customer_phones(tenant_id, e164)`
- Location city / postal indexes

## Pagination

Keyset cursor (`updated_at`, `id`) for empty-query lists. Search pages through ranked results with the same cursor encoding. Hard max limit **200**.

## Isolation

Every query includes `tenant_id`. Archived customers are excluded unless `include_archived=true`.

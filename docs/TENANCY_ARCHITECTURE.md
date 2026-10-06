# Tenancy Architecture

**Date:** 2026-10-06  
**Canonical tenant key:** `tenant_id` (UUID). Treat as `organization_id` in product language; do not add a parallel `organizations` table.

---

## 1. Tenant resolution

Tenant identity must come from a trusted principal — never from an unauthenticated client field alone.

| Surface | Resolution | Trusted? |
|---------|------------|----------|
| Ops console | Session JWT → `tenant_id` + DB user re-check | Yes |
| Public API (`/v1`) | API key hash → `TenantApiKey.tenant_id` | Yes |
| Voice SIP inbound | DID / trunk → `tenant_phone_numbers` (fail-closed) | Yes |
| Voice tools | `SessionUserData.tenant_id` after resolve; LLM override rejected | Yes |
| Internal service | `X-Internal-Token` + explicit `tenant_id` in path/body | Partially — shared token is god-mode; bind call-scoped claims next |
| Legacy telephony `/tenants/{id}/…` | Must require internal token (or ops session); path id alone is insufficient | Required |

### Rules

1. Never trust frontend-supplied `tenant_id` for authorization.
2. Ops write APIs use `CurrentUser.tenant_id` from the session.
3. Reject request bodies that attempt to override tenant (`extra: "forbid"` where applicable).
4. Background work must receive `tenant_id` in the job/event payload and re-filter every query.
5. Cache keys must include `tenant_id` for tenant-owned data.

---

## 2. Tenant isolation

### Application layer (current primary control)

```text
Authenticated principal
        ↓
TenantContext(tenant_id, source)
        ↓
Repository.query(...).where(Model.tenant_id == tenant_id)
        ↓
Optional ownership check on child FKs (customer_id, job_id, …)
```

Every tenant-owned table includes `tenant_id` (except platform-global `stripe_webhook_events` and root `tenants`).

Unique constraints that are business-local are tenant-aware:

```text
UNIQUE (tenant_id, e164)          -- customer_phones
UNIQUE (tenant_id, slug)          -- agent_profiles
UNIQUE (tenant_id, idempotency_key)
UNIQUE (tenant_id)                -- organization_onboarding / organization_crm_configurations
UNIQUE (tenant_id, module_key)    -- organization_crm_modules
```

Global uniqueness is intentional only where the resource is globally unique (e.g. phone DID inventory: `UNIQUE (e164)` on `tenant_phone_numbers`).

Business profile fields live on `tenants` (Identity). Platform industry CRM templates are **code registries**, not tenant-mutable rows — see `docs/CRM_CONFIGURATION.md`.

### Defense in depth (planned)

- Postgres RLS policies keyed by `SET LOCAL app.tenant_id`
- Per-tenant or per-call internal tokens (not one shared token)
- Frozen session userdata for voice (`tenant_id` immutable)

### Isolation must cover

- Reads, updates, deletes
- List/search endpoints
- Admin exports
- Cache get/set
- Async consumers
- File object keys (`tenant/{tenant_id}/…`)

---

## 3. Shared database strategy (default)

```text
All tenants → single PostgreSQL database → shared schema
Isolation → tenant_id column + application filters (+ future RLS)
```

**Use for:** small/medium tenants, all current production scale assumptions.

**Pros:** operational simplicity, cheap joins for modular monolith, single migration stream.  
**Cons:** noisy-neighbor risk; one schema bug can affect all tenants if filters are forgotten.

Connection pooling is shared (`QueuePool` with configured bounds). Do not open a new engine per request or per tenant in shared mode.

---

## 4. Dedicated database strategy (enterprise)

```text
Tenant Resolver
      ↓
Tenant Database Strategy
      ↓
  shared  → default DATABASE_URL
  dedicated → DSN from secret store keyed by tenants.db_dsn_key
```

### Schema on `tenants`

| Column | Purpose |
|--------|---------|
| `db_strategy` | `shared` (default) \| `dedicated` |
| `db_dsn_key` | Opaque key into secrets manager (never store raw DSN in the row) |

### Runtime

`TenantDatabaseResolver.resolve(tenant_id)` returns a bind URL / engine handle.

- Shared tenants → process-wide default engine.
- Dedicated tenants → lazy engine from a **bounded** cache (idle timeout; do not hold a large pool forever for inactive tenants).

Repositories should obtain sessions via the resolver, not `create_engine` ad hoc.

### When to migrate a tenant to dedicated

- Sustained high call volume or storage
- Compliance / data residency
- Custom backup / restore SLA
- Noisy-neighbor incidents

---

## 5. Tenant migration strategy (shared → dedicated)

1. Provision empty dedicated DB; run migrations to head.
2. Copy tenant-scoped rows in FK-safe order (tenants row first, then children).
3. Dual-write or freeze writes briefly; verify row counts and checksums.
4. Flip `db_strategy` + `db_dsn_key`; drain in-flight jobs on old DB.
5. Keep shared copy read-only backup until retention window ends; then delete.

**Never** migrate by editing production tables manually. Use scripted, reversible, tested cutovers.

---

## 6. Request-scoped context

```python
# callbot_platform.tenancy.context
TenantContext(tenant_id, source: session | api_key | sip | internal | job)
```

Set at the API/auth boundary; clear after the request. Repositories may assert context matches the `tenant_id` argument to catch accidental cross-tenant bugs in development.

---

## 7. Testing requirements

Integration tests (real DB) must prove:

- Tenant A cannot read / update / delete Tenant B rows
- Ops session cannot act on another tenant’s path id
- Unauthenticated telephony mutations fail
- Redis profile cache rejects cross-tenant payloads
- Voice tools ignore client `tenant_id` overrides

See `platform/tests/test_tenant_isolation.py` and the full ownership matrix in `docs/TENANT_ISOLATION_AUDIT.md`. Also: existing CRM/jobs/scheduling isolation cases.

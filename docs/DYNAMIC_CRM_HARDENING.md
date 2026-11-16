# Dynamic CRM Hardening (Task 3.5)

**Date:** 2026-10-06  
**Staging:** NOT EXECUTED (fleet NOT AVAILABLE)

---

## Audit summary

| Component | Severity | Change |
|-----------|----------|--------|
| Effective config | P2 | Tenant-scoped in-process TTL cache + invalidate |
| Filter AST | P1 | LIKE escape, typed coerce, ADDRESS→JSON, reject extra keys |
| Relationships | P1 | PLATFORM_ENTITY / CUSTOM_OBJECT / CONFIGURATION_ONLY |
| Field path IDOR | P1 | `require_field_for_owner` |
| Pagination | P1 | `Query(le=200)`; remove silent 1000 ID fetch |
| Audit | P1 | Record update audited |
| Indexes | P2 | Migration `0029` date/datetime/boolean |

---

## Cache

Key: `tenant:{tenant_id}:crm:effective_configuration` (process-local, 60s TTL).

Invalidated on module / field / object definition / relationship definition / CRM setup mutations.

**Does not cache authorization.** Redis unavailable → no platform Redis CRM cache; process cache miss loads Postgres.

---

## Soft archive

- Archived custom-object records excluded from normal lists and new relationship links.
- Disabling an object definition invalidates config cache; existing links are preserved.
- Historical relationship edges are not cascade-deleted.

---

## Staging runbook

1. Backup staging DB  
2. Apply `0028` then `0029`  
3. Verify schema/indexes  
4. Run RBAC reconcile (`reconcile_all_tenants` / existing ops path)  
5. For orgs with industry+model: optional `CrmSetupService.setup` (idempotent)  
6. Smoke: modules, fields, objects, relationships, navigation  
7. Confirm tenant isolation + Redis/cache miss path  
8. Monitor latency/errors  

Do **not** run against production.

---

## Phase 4 gate

```text
NOT READY FOR PHASE 4
```

Reason: staging verification still NOT AVAILABLE / NOT EXECUTED.

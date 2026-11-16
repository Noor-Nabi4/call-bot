# Dynamic CRM Architecture (Phase 3)

**Date:** 2026-10-06  
**Scope:** Metadata-driven CRM configuration engine — not Phase 4 commerce domain CRUD.

---

## Effective configuration

```text
Platform module registry (code)
        + industry template (CrmSetupService)
        + organization_crm_modules overrides
        + organization_crm_fields
        + custom object definitions
        + relationship definitions
        = EffectiveCrmConfigurationService.get(tenant_id)
```

API: `GET /api/admin/crm/configuration`

Frontend navigation consumes `configuration.navigation` (enabled modules + custom objects), filtered by existing RBAC helpers.

Caching: tenant-scoped in-process TTL (`docs/DYNAMIC_CRM_HARDENING.md`). Authorization is never cached here.

---

## Storage principles

- **No giant universal CRM table** for platform entities.
- Core entities (`customers`, `jobs`, …) remain relational.
- Organization-defined fields use typed EAV: `organization_crm_fields` + `crm_custom_field_values`.
- Custom objects: definition + record identity tables; business fields via EAV.
- Relationships: definition + link tables (supports 1:1, 1:N, N:N).

See also:

- `docs/CRM_MODULES.md`
- `docs/CUSTOM_FIELDS.md`
- `docs/CUSTOM_OBJECTS.md`
- `docs/CRM_RELATIONSHIPS.md`
- `docs/DYNAMIC_CRM_HARDENING.md`

---

## Permissions

| Key | Purpose |
|-----|---------|
| `crm.configure` | Enable/disable/reorder modules; field & relationship schema |
| `custom_objects.read` / `custom_objects.manage` | Custom object definitions & records |
| Module `*.read/create/update/delete` | Catalog-mapped per module |

Tenant always from session. Disabling a module hides navigation; it does **not** delete data.

---

## Search / filter

Controlled filter AST → parameterized SQL against typed value columns. Unsupported operators and malicious AST keys are rejected. No client SQL.

---

## Phase 4 gate

`docs/PRODUCTION_READINESS.md` remains `NOT READY FOR PHASE 4`. This engine does not implement Products/Orders/Invoices domain tables.

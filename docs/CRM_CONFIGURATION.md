# CRM Configuration (Tasks 2.4–2.5)

**Date:** 2026-10-06  
**Scope:** Configuration metadata only — not Phase 3/4 domain CRUD.

---

## Template vs organization configuration

```text
Platform CRM template (immutable code registry)
        ↓ resolve(industry, business_model)
Tenant organization_crm_* tables (tenant-owned copy)
```

Tenants cannot mutate global templates. Setup **creates missing** defaults and **preserves** rows with `source=custom` (and does not force-re-enable custom-disabled modules).

---

## Platform templates

Package: `callbot_platform.crm_templates`

Each template defines: modules, settings, statuses, fields, workflows, version.

Resolver: `resolve_template(industry_key, business_model)`.

API (read-only catalog):

- `GET /api/admin/organization/industry-templates`
- `GET /api/admin/organization/industry-templates/{key}`

---

## Tenant tables

| Table | Uniqueness |
|-------|------------|
| `organization_crm_configurations` | `tenant_id` |
| `organization_crm_modules` | `(tenant_id, module_key)` |
| `organization_crm_statuses` | `(tenant_id, module_key, status_key)` |
| `organization_crm_fields` | `(tenant_id, module_key, field_key)` |
| `organization_crm_workflows` | `(tenant_id, workflow_key)` |

Migration: `0027_business_crm_configuration`.

---

## Setup service

`CrmSetupService.setup(tenant_id, actor=…)`:

1. Read tenant industry + business model  
2. Resolve template  
3. Upsert configuration row  
4. Insert missing modules/statuses/fields/workflows  
5. Merge missing settings keys only  

Idempotent: safe to call repeatedly.

API:

- `GET /api/admin/organization/crm-configuration`
- `POST /api/admin/organization/crm-configuration/setup`

---

## Onboarding completion

`OnboardingService.mark_completed` / auto-complete on last required step:

1. Validate required steps  
2. Require name + industry + business model  
3. Run CRM setup  
4. Mark onboarding `COMPLETED`  

If setup fails, onboarding does **not** complete.

---

## Module keys

Registry: `callbot_platform.business_config.modules` (`CUSTOMERS`, `JOBS`, …).

Enabling a module does **not** implement its CRUD — Phase 3/4 owns product surfaces.

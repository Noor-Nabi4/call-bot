# Onboarding Architecture (Task 2.1)

**Date:** 2026-10-06  
**Ownership:** Identity / Organization (tenant-owned workflow state)  
**Not:** telephony `onboarding_path`, signup checkout, or domain entity storage

---

## Ownership

```text
Authenticated User
        ↓
Organization Membership + RBAC
        ↓
TenantContext (session tenant_id)
        ↓
organization_onboarding (1 row per tenant)
```

Client-supplied `tenant_id` is never authoritative. APIs use `CurrentUser.tenant_id` only.

---

## State model

Table: `organization_onboarding` (`UNIQUE(tenant_id)`)

| Column | Purpose |
|--------|---------|
| `status` | `NOT_STARTED` \| `IN_PROGRESS` \| `COMPLETED` \| `SKIPPED` |
| `current_step` | Canonical step key for resume |
| `completed_steps` | JSON list of completed step keys |
| `skipped_steps` | JSON list of skipped **optional** step keys |
| `progress_percent` | Derived, persisted for cheap reads |
| `state_data` | Shallow draft bag for wizard-only notes (not domain entities) |
| `started_at` / `completed_at` | Lifecycle timestamps |

Lazy create on first `GET`/`PATCH`.

### Transitions

```text
NOT_STARTED → IN_PROGRESS   (first meaningful save / step action)
NOT_STARTED → SKIPPED       (skip entire wizard)
IN_PROGRESS → COMPLETED     (all required steps complete, or POST /complete)
IN_PROGRESS → SKIPPED       (skip entire wizard)
COMPLETED / SKIPPED → closed (mutations denied)
```

No restart/reset in Task 2.1.

---

## Step registry

Canonical ordered registry: `callbot_platform.onboarding.steps.ONBOARDING_STEPS`.

Keys (Phase 2 roadmap-aligned):

```text
business_profile*  industry*  business_model*  catalog
customers  business_hours*  team  ai_configuration*
knowledge  phone_setup  review*
```

`*` = required. Optional steps may be skipped; required steps cannot.

Future tasks (2.2+) may filter applicability by industry/business model **without** changing the persistence schema — only the registry/applicability layer.

---

## Progress

```text
settled = completed_steps ∪ skipped_steps (optional only)
progress_percent = round(100 * |settled ∩ STEP_ORDER| / |STEP_ORDER|)
completed_count = |settled ∩ STEP_ORDER|
total_count = |STEP_ORDER|
```

Skipped optional steps count toward progress so optional work does not leave the bar stuck. Skipped steps are **not** completed. Clients cannot submit arbitrary `progress_percent`.

---

## Resume

Response includes:

- `current_step`
- `resume_step` (repaired if stale/invalid → first pending)
- `can_resume` (`IN_PROGRESS` and a pending step exists)

Authoritative source is the database, not localStorage/URL.

---

## API

Prefix: `/api/admin/organization/onboarding`

| Method | Path | Permission |
|--------|------|------------|
| GET | `` | `organization.read` |
| PATCH | `` | `organization.update` |
| POST | `/steps/{step}/complete` | `organization.update` |
| POST | `/steps/{step}/skip` | `organization.update` |
| POST | `/complete` | `organization.update` |
| POST | `/skip` | `organization.update` |

Uses `require_permission` (not entitled) so onboarding works before subscription activation — same pattern as organization profile.

PATCH body (`extra=forbid`):

```json
{ "current_step": "industry", "state_data": { "draft_note": "…" } }
```

`state_data` is shallow-merged; `null` values remove keys.

---

## RBAC

- Read: `organization.read`
- Mutate: `organization.update`
- No new permission keys
- Technicians / dispatchers without org update cannot mutate

---

## Tenant isolation

All queries filter `tenant_id = session.tenant_id`. One row per tenant. Cross-tenant IDOR tests in `platform/tests/test_onboarding.py`.

---

## Idempotency & concurrency

- Completing/skipping the same step repeatedly is a no-op (set semantics).
- Mutations load with `FOR UPDATE` where supported.
- Completing the last required step auto-sets `COMPLETED`.

---

## Frontend

- `/onboarding` — load state, progress, resume, draft save, complete/skip steps
- Nav item gated by `organization.read`
- Step UIs for Task 2.2+ will write domain tables and then call complete-step

---

## Future tasks

| Task | Should |
|------|--------|
| 2.2 Business info | Persist to `tenants` profile fields; call `complete` on `business_profile` / `industry` / … |
| Catalog / knowledge / phones | Use real domain APIs; only mark steps here |
| Do not | Dump Business OS into `state_data` |

See also: `docs/DATA_OWNERSHIP.md`, `docs/TENANT_ISOLATION_AUDIT.md`.

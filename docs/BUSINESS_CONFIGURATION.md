# Business Configuration (Tasks 2.2–2.3)

**Date:** 2026-10-06  
**Canonical profile storage:** `tenants` row (organization entity)  
**Onboarding workflow:** `organization_onboarding` (Task 2.1)

---

## Ownership

Session `tenant_id` → organization profile fields on `tenants`. No client-supplied tenant ids.

Permissions: `organization.read` / `organization.update`.

---

## Business profile (Task 2.2)

Fields on `tenants`:

| Field | Notes |
|-------|-------|
| `name` | Business name |
| `industry_key` | Canonical industry key |
| `country`, `state`, `timezone`, `currency` | Locale |
| `website`, `phone`, `email` | Contact |
| `business_size` | `solo` \| `small` \| `medium` \| `large` \| `enterprise` |
| `business_type` | Business **model** key (see below) |

**Industry ≠ business type.** Industry is vertical (`hvac`). Business type/model is how they sell (`services`).

API:

- `GET/PATCH /api/admin/organization/business-profile`
- Catalogs returned with GET (industries, models, sizes)
- PATCH may include `complete_steps` to advance onboarding

---

## Business model (Task 2.3)

Stored as `tenants.business_type`.

Keys: `products`, `services`, `products_and_services`, `subscriptions`, `appointments`, `rentals`, `custom`.

API: `GET/PUT /api/admin/organization/business-model` (PUT also completes the `business_model` onboarding step).

---

## Industry keys

Machine keys (not display names): `hvac`, `plumbing`, `electrical`, `cleaning`, `automotive`, `dental`, `medical`, `real_estate`, `ecommerce`, `consulting`, `beauty_salon`, `fitness`, `custom`.

Registry: `callbot_platform.business_config.industries`.

---

## Validation

Authoritative in `organization/validation.py` (+ catalog membership for industry/size).

Existing organizations are **not** auto-assigned industry/model/size.

# Platform vs Organization Authorization

**Hard rule:** Organization Owner is **not** Call & Flow Platform Owner.

```text
Customer Organization Owner
= highest authority INSIDE one tenant

Call & Flow Platform Owner / Operator
= authority over the SaaS platform (separate boundary)
```

An Enterprise subscription does **not** grant platform administration.

---

## Authorization hierarchy

### Organization domain

```text
Authenticated principal
→ Organization membership
→ TenantContext (tenant_id)
→ Organization role (Owner, Admin, …)
→ Organization permission
→ Permission scope
→ Resource ownership / assignment
→ ALLOW / DENY
```

### Platform domain

```text
Platform principal (today: X-Internal-Token / require_platform_operator)
→ Platform permission keys (PLATFORM_PERMISSION_KEYS — not seeded onto org roles)
→ ALLOW / DENY
```

These domains must not cross via `role == "Owner"`.

---

## Organization roles

Seeded system roles (`rbac/catalog.py`): Owner, Admin, Manager, Dispatcher, Technician, CSR, Accountant, AI Agent.

They operate **only** inside their organization: CRM, jobs, billing subscription/usage limits, agents, knowledge, integrations, org settings, members, roles, org-scoped audit.

`SYSTEM_ROLE_OWNER` receives all **organization** catalog permissions — never `PLATFORM_PERMISSION_KEYS`.

---

## Platform roles / permissions

`PLATFORM_PERMISSION_KEYS` documents intended platform capabilities (`platform.cogs.read`, `platform.revenue.read`, …).

They are:

* **not** part of `PERMISSION_CATALOG`
* **never** granted by `default_role_permissions`
* **not** assignable through organization RBAC APIs today

**Enforcement today:** `require_platform_operator` → `X-Internal-Token` (`INTERNAL_SERVICE_TOKEN`).  
Future human Platform Owner/Admin sessions must remain outside organization role templates.

---

## API classification

| Class | Examples | Gate |
|-------|----------|------|
| Organization admin | Most `/api/admin/*` CRM/team/billing usage | Session + org permission + tenant |
| Customer usage | `GET /api/admin/usage-cost/summary`, `/usage-cost/alerts` | `billing.read` — **customer DTO only** |
| Platform COGS / finance | `/api/admin/cogs/*`, `/usage-cost/platform-summary`, `/usage-cost/fleet` | `require_platform_operator` |
| Internal service | Telephony, call-scope, bootstrap | Internal token (+ call-scope where required) |
| Webhooks | Stripe, Twilio | Provider signature |

`/api/admin` **does not** mean platform admin. Many routes are organization admin.

---

## Phase 32 visibility

### Organization may see

* Own voice / LLM / AI / tool / SMS / transcription / storage usage
* Plan limits, usage alerts, estimated overage
* Own billing subscription status (via billing APIs)

DTO: `UsageCostAggregationService.customer_usage_summary` → `boundary: organization`.

### Organization must NOT see

* OpenAI / Twilio / LiveKit / infrastructure COGS
* Provider rate cards / scenarios
* Platform revenue, gross margin, fleet rollups
* Other tenants’ usage or costs

DTO: `organization_summary` / COGS services — platform routes only.

---

## Phase 33 visibility

### Organization may see

* Own members, roles, permissions
* Own API keys, integrations
* Own org-scoped audit/activity where already exposed

### Organization must NOT see

* Platform security architecture, rate-limit internals, encryption keys, webhook secrets, platform-wide audit, provider credentials

---

## Frontend

| Surface | Audience |
|---------|----------|
| `/settings/usage` | Organization — consumption & limits |
| `/settings/billing` | Organization — subscription |
| `/settings/cogs` | Redirects to `/settings/usage` (no COGS UI) |
| Nav label “Usage” | `billing.read` — never “COGS & Profitability” |
| Future `/platform/*` | Platform operators only (not built yet) |

UI hiding is never authorization. APIs enforce the boundary.

---

## AI agents

Agents for Organization A follow the same org RBAC + tenant + Phase 14/30/31 pipeline. They must not access platform COGS, other tenants, or platform secrets.

---

## Future phases (34+)

Classify every feature:

* **CUSTOMER-FACING** — org RBAC + tenant scope
* **PLATFORM-INTERNAL** — platform operator gate
* **BOTH** — separate org view and platform view DTOs/routes; never share leaking serializers

---

## Mandatory Rule for Future Phases

Before implementing any new feature, determine whether its data or functionality is:

```text
CUSTOMER-FACING
PLATFORM-INTERNAL
BOTH
```

### CUSTOMER-FACING

Use:

```text
Organization RBAC
+
TenantContext
+
Organization permissions
+
Resource scope
```

Expose only organization-safe information. Never use `role == "Owner"` as platform authority.

### PLATFORM-INTERNAL

Use:

```text
require_platform_operator (or future platform RBAC)
+
PLATFORM_PERMISSION_KEYS
```

Never seed platform permissions into `PERMISSION_CATALOG` or organization roles.

### BOTH

Create explicit separation:

```text
Customer API/DTO  ≠  Platform API/DTO
Customer UI       ≠  Platform UI
```

Do **not** expose platform data by reusing a broader serializer and hiding fields in the UI.

Example (usage):

```text
Organization view → customer_usage_summary (usage, limits, estimated overage)
Platform view     → organization_summary / COGS / margin / fleet
```

A customer on any plan, including Enterprise, must never gain Call & Flow internal profit, COGS, provider economics, platform security internals, or other organizations' data.

---

## Testing

* `tests/test_platform_org_boundary.py` — Owner cannot call platform COGS; customer DTO omits financials; platform token can
* Existing Phase 14/30/31/32/33, RBAC, isolation suites remain required regressions

---

## Verification status

| Layer | Status |
|-------|--------|
| APPLICATION IMPLEMENTATION | Complete (this change) |
| APPLICATION SECURITY TESTS | Local pytest |
| LOCAL VERIFICATION | Application tests |
| STAGING VERIFICATION | NOT EXECUTED |
| LIVE PROVIDER VERIFICATION | BLOCKED |
| PRODUCTION READINESS | BLOCKED until staging/live drills |

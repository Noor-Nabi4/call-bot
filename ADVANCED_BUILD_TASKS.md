# AI Business OS — Advanced Build Tasks

## Product Vision

Build a multi-tenant, AI-first Business Operating System that can adapt itself to different businesses.

The platform should support:

- CRM
- Products
- Services
- Inventory
- Orders
- Leads
- Jobs
- Appointments
- Dispatch
- Technicians
- Estimates
- Invoices
- Payments
- Memberships
- Equipment
- AI Voice Agent
- AI SMS Agent
- AI Knowledge Base
- Automations
- Analytics
- Integrations

The system must NOT assume every business is the same.

A business should configure its CRM and AI behavior during onboarding.

---

# GLOBAL DEVELOPMENT RULES

Before starting any task:

- [ ] Inspect the existing repository
- [ ] Understand the current architecture
- [ ] Reuse existing patterns
- [ ] Do not duplicate existing functionality
- [ ] Do not introduce unnecessary dependencies
- [ ] Do not use mock data for production functionality
- [ ] Preserve existing functionality

Architecture principles:

- Authorization must be enforced server-side. Frontend permission checks are only for UI behavior. Organization Admin/Owner can manage organization roles and assignments, but cannot create arbitrary platform permissions or bypass protected platform/Owner security boundaries.
- AI agents and AI tools must use the same organization authorization model as human users. AI must never bypass RBAC.

For every completed task:

- [ ] Database changes implemented
- [ ] Migration created if required
- [ ] Backend implemented
- [ ] API implemented
- [ ] Authorization implemented
- [ ] Frontend implemented if required
- [ ] Validation implemented
- [ ] Loading state implemented
- [ ] Empty state implemented
- [ ] Error state implemented
- [ ] Tests added
- [ ] Existing tests pass
- [ ] Lint passes
- [ ] Build passes
- [ ] No TypeScript errors
- [ ] No regression
- [ ] Documentation updated
- [ ] Mark task complete only after verification

---

# PHASE 0 — ARCHITECTURE AUDIT

## TASK 0.1 — Repository Audit

### Description

Understand the current application before modifying anything.

### Checklist

- [x] Identify frontend
- [x] Identify backend
- [x] Identify database
- [x] Identify authentication
- [x] Identify existing tenant/business model
- [x] Identify existing users
- [x] Identify existing calls
- [x] Identify existing voice agent
- [x] Identify Twilio implementation
- [x] Identify LiveKit implementation
- [x] Identify OpenAI implementation
- [x] Identify Stripe implementation
- [x] Identify SMS implementation
- [x] Identify email implementation
- [x] Identify existing CRM
- [x] Identify existing calendar
- [x] Identify existing background jobs
- [x] Identify queues/events
- [x] Identify existing integrations

### Deliverable

Created:

[`docs/ARCHITECTURE_AUDIT.md`](./docs/ARCHITECTURE_AUDIT.md)

---

# PHASE 1 — MULTI-TENANT FOUNDATION

## TASK 1.1 — Organization Model

### Description

Create the main business/tenant entity.

### Fields

- `id`
- `name`
- `slug`
- `industry`
- `business_type`
- `timezone`
- `currency`
- `country`
- `state`
- `website`
- `phone`
- `email`
- `status`
- `created_at`
- `updated_at`

### Checklist

- [x] Database table
- [x] Migration
- [x] Entity/model
- [x] Repository
- [x] Service
- [x] API
- [x] Validation
- [x] Tests

---

## TASK 1.2 — Organization Membership

### Description

Connect users with businesses.

Reuse `tenant_users` as the organization membership table (unique `tenant_id` + `email`). Do not create a parallel `organization_members` table. Role remains a string until Task 1.3.

### Checklist

- [x] Membership table
- [x] User relationship
- [x] Organization relationship
- [x] Role
- [x] Status
- [x] Unique constraint
- [x] API
- [x] Authorization tests

---

## TASK 1.3 — Organization-Managed RBAC

### Description

Implement a flexible organization-level role and permission system.

The platform defines the available **permissions**, while each organization can manage its own roles and assign permissions to its users.

Organizations should be able to:

- View available permissions
- Use predefined system roles
- Create custom roles
- Rename custom roles
- Assign permissions to roles
- Remove permissions from roles
- Assign roles to organization members
- Remove roles from members
- Manage role membership
- Disable/deactivate custom roles
- View role assignments
- Audit role and permission changes

The platform must NOT allow organizations to create arbitrary permissions.

Permissions are defined centrally by the platform.

---

### System roles

Provide predefined roles as starting templates:

- Owner
- Admin
- Manager
- Dispatcher
- Technician
- CSR
- Accountant

These should be organization-scoped role assignments.

Organizations may customize permissions for appropriate roles where allowed.

The `Owner` role must remain protected.

Do not allow an Admin or custom role to:

- remove the Owner
- modify the Owner's authority
- grant themselves Owner
- bypass platform-level security
- grant permissions they are not authorized to delegate

---

### Custom roles

Organizations should be able to create custom roles.

Examples:

- Sales Representative
- Office Manager
- Support Manager
- Field Supervisor
- Warehouse Manager
- Billing Specialist
- Marketing Manager

Custom roles must belong to exactly one organization.

A custom role must contain:

- `id`
- `organization_id`
- `name`
- `description`
- `status`
- `created_at`
- `updated_at`

Do not create separate database tables for every role.

---

### Platform permissions

Permissions should be centrally defined.

Use a consistent naming convention:

```text
resource.action
```

Examples:

```text
customers.read
customers.create
customers.update
customers.delete

leads.read
leads.create
leads.update
leads.delete

products.read
products.create
products.update
products.delete

inventory.read
inventory.adjust

orders.read
orders.create
orders.update
orders.cancel

jobs.read
jobs.create
jobs.update
jobs.assign

appointments.read
appointments.create
appointments.update
appointments.cancel

technicians.read
technicians.manage

estimates.read
estimates.create
estimates.send

invoices.read
invoices.create
invoices.send

payments.read
payments.create
payments.refund

ai.read
ai.configure

knowledge.read
knowledge.manage

automations.read
automations.manage

integrations.read
integrations.manage

analytics.read

organization.read
organization.update

members.read
members.invite
members.update
members.remove

roles.read
roles.create
roles.update
roles.delete
roles.assign
```

The exact permission catalog should be finalized during implementation based on the actual modules available.

Do not duplicate permissions across modules.

---

### Role → permission model

Use a normalized relationship:

```text
Organization
    │
    └── Roles
          │
          └── Role Permissions
                  │
                  └── Platform Permissions
```

And:

```text
Organization
    │
    └── Members
          │
          └── Role Assignments
                  │
                  └── Organization Roles
```

Avoid putting permissions into a JSON blob if a normalized relationship is more appropriate for authorization queries.

Do not create one giant RBAC table containing every possible user/role/permission combination.

---

### Permission scope

Design the authorization model so that permissions can support scope.

Initial scopes:

```text
ALL_ORGANIZATION
OWN
ASSIGNED
TEAM
```

Examples:

```text
Technician

jobs.read       → ASSIGNED
jobs.update     → ASSIGNED
customers.read  → ASSIGNED
```

Manager:

```text
jobs.read       → ALL_ORGANIZATION
jobs.update     → ALL_ORGANIZATION
customers.read  → ALL_ORGANIZATION
```

Do not over-engineer complex attribute-based access control at this stage.

The architecture should allow scope to be introduced without redesigning the entire authorization system.

---

### Role hierarchy / delegation

Do not create an unrestricted role hierarchy.

Instead, define safe delegation rules.

An organization member may only:

- assign roles they are authorized to assign
- grant permissions they are authorized to delegate
- modify roles within their administrative scope

Owner has full organization administration authority.

Admin may manage organization users and roles according to its assigned permissions.

Manager and lower roles must not automatically gain role-management capabilities.

Never allow privilege escalation.

---

### Organization admin UI

The future UI should provide:

```text
Settings
  └── Team & Permissions
        │
        ├── Members
        │
        ├── Roles
        │     ├── Owner
        │     ├── Admin
        │     ├── Manager
        │     ├── Dispatcher
        │     ├── Technician
        │     ├── CSR
        │     ├── Accountant
        │     └── Custom Roles
        │
        └── Permissions
```

Role editor:

```text
Role: Dispatcher

Customers
  ☑ View

Jobs
  ☑ View
  ☑ Create
  ☑ Update
  ☑ Assign

Appointments
  ☑ View
  ☑ Create
  ☑ Update
  ☑ Cancel

Invoices
  ☐ Create
  ☐ Send

Payments
  ☐ Refund

AI
  ☐ Configure
```

The UI should only display permissions available to that organization and should prevent unauthorized privilege escalation.

---

### Authorization architecture

All backend authorization must ultimately resolve:

```text
Authenticated User
        ↓
Organization Membership
        ↓
Assigned Role(s)
        ↓
Role Permissions
        ↓
Permission Scope
        ↓
Resource Ownership / Organization
        ↓
ALLOW / DENY
```

Never rely only on frontend permission checks.

Frontend checks are for UX.

Backend authorization is authoritative.

AI agents and internal tools must use the same authorization model.

---

### AI agent authorization

The RBAC system must also support AI actions.

Example:

```text
AI Agent
    ↓
Organization
    ↓
Agent Permissions
    ↓
Tool Permission
    ↓
Resource Scope
    ↓
Tool Execution
```

For example:

An AI receptionist may have:

```text
customers.read
customers.create

appointments.read
appointments.create
appointments.update

services.read

jobs.create

send_sms
```

But not:

```text
payments.refund
organization.delete
members.remove
roles.assign
```

AI must never bypass organization RBAC.

Tool-level authorization remains mandatory even when the tool is called by the voice/SMS agent.

---

### RBAC database design

The implementation plan should anticipate these concepts:

```text
permissions
organization_roles
role_permissions
organization_members
member_roles
```

If the existing architecture already has equivalent tables/models, reuse them instead of creating duplicates.

Possible conceptual structure:

```text
permissions
------------
id
key
description
resource
action
system_defined
created_at


organization_roles
------------------
id
organization_id
name
description
is_system_role
status
created_at
updated_at


role_permissions
----------------
role_id
permission_id
scope
created_at


member_roles
------------
member_id
role_id
created_at
```

Do not blindly implement these exact fields if the existing architecture suggests a better equivalent.

Current codebase mapping (from architecture audit; do not implement in this planning task):

- Organization ≈ `tenants`
- Members ≈ `tenant_users`
- Existing string roles (`admin`, `dispatcher`, `technician`) must migrate into organization-scoped role assignments without locking operators out

---

### Security requirements

The implementation must include tests for:

#### Tenant isolation

Organization A cannot:

- read Organization B roles
- read Organization B permissions assigned to roles
- modify Organization B roles
- assign Organization B roles
- assign permissions to Organization B roles

#### Privilege escalation

Test that:

- Admin cannot make themselves Owner
- Manager cannot grant themselves Admin
- Technician cannot assign roles
- Custom roles cannot bypass authorization
- A user cannot grant a permission they cannot delegate

#### AI security

Test that:

- AI cannot execute unauthorized tools
- AI cannot bypass RBAC
- AI cannot access another organization
- AI cannot perform destructive operations without required permission

#### Backend enforcement

Test that direct API requests fail even if the frontend permission check is bypassed.

---

### Audit logging

Role and permission changes must be auditable.

Record events such as:

```text
ROLE_CREATED
ROLE_UPDATED
ROLE_DELETED
ROLE_PERMISSION_GRANTED
ROLE_PERMISSION_REVOKED
MEMBER_ROLE_ASSIGNED
MEMBER_ROLE_REMOVED
```

Audit records should include:

- organization
- actor
- action
- target
- timestamp
- relevant metadata

Never log secrets.

---

### Checklist

- [x] Platform permission catalog (`resource.action`)
- [x] Organization-scoped system roles (Owner protected)
- [x] Custom organization roles
- [x] Normalized role ↔ permission assignments with scope
- [x] Member ↔ role assignments
- [x] Safe delegation (no privilege escalation)
- [x] Server-side authorization (API + AI tools)
- [x] Ops UI: Team & Permissions (UX only; backend authoritative)
- [x] RBAC audit events
- [x] Tenant isolation tests
- [x] Privilege escalation tests
- [x] AI/tool authorization tests
- [x] Direct API bypass tests

See also: [`docs/RBAC_ARCHITECTURE.md`](./docs/RBAC_ARCHITECTURE.md)

---

## TASK 1.3.1 — Migrate Legacy Authorization to RBAC

### Description

Replace remaining `require_ops_roles` / `user.role` security gates with capability permissions. Keep `tenant_users.role` as a compatibility field only.

### Checklist

- [x] Repository-wide legacy auth audit (`docs/RBAC_LEGACY_AUTH_AUDIT.md`)
- [x] Jobs routes migrated to permissions + ResourceContext
- [x] Billing routes migrated (`billing.read` / `billing.manage`)
- [x] Admin / knowledge / handoff / automation / branding / API keys / agents / phones migrated
- [x] Deprecated `require_ops_roles` unused by routes
- [x] Legacy role string not authoritative when `member_roles` present
- [x] Regression tests for migrated domains

---

## TASK 1.3.2 — Fail-Closed Scoped Authorization

### Description

Scoped permissions (`OWN`, `ASSIGNED`, `TEAM`) must deny when `ResourceContext` is missing or incomplete. Organization-wide grants remain usable for list/create without a resource.

### Checklist

- [x] `AuthorizationService.has_permission` fail-closed for scoped grants
- [x] List access via `list_access_mode` (all / assigned / deny)
- [x] Jobs get/update/checklist/notes load resource then authorize
- [x] Cross-tenant resource tenant mismatch denied
- [x] Scope regression tests (ASSIGNED / OWN / TEAM / missing context)

See also: [`docs/RBAC_LEGACY_AUTH_AUDIT.md`](./docs/RBAC_LEGACY_AUTH_AUDIT.md)

---

## TASK 1.3.3 — RBAC Reconciliation + Frontend Permission Migration

### Description

Safely reconcile system-role defaults for long-lived organizations without restoring intentional revocations. Migrate frontend UX gates from JWT/legacy role strings to effective RBAC permissions. Backend remains authoritative.

### Checklist

- [x] Implementation complete
- [x] Local verification complete
- [x] Security regression coverage complete (tombstone lifecycle + session RBAC cache)
- [x] `role_permissions.source` + `role_permission_tombstones` (migration `0025`)
- [x] Idempotent `reconcile_system_roles_for_tenant` / freeze-gaps upgrade path
- [x] Intentional revocations preserved; custom roles/scopes untouched
- [x] `/auth/me` + `/auth/me/permissions` return effective roles/permissions
- [x] Frontend `hasPermission` / `useAuth({ permission })` / nav / forbidden UX
- [x] Legacy JWT `role` kept for compatibility/display only (not authorization)
- [x] Docs: `docs/RBAC_RECONCILIATION.md`, `docs/RBAC_STAGING_VERIFICATION.md`, legacy auth audit
- [ ] Staging migration
- [ ] Staging RBAC E2E
- [ ] Browser E2E

See also: [`docs/RBAC_RECONCILIATION.md`](./docs/RBAC_RECONCILIATION.md), [`docs/RBAC_STAGING_VERIFICATION.md`](./docs/RBAC_STAGING_VERIFICATION.md)

---

## TASK 1.4 — Tenant Isolation

### Description

Every business must only access its own data.

### Checklist

- [x] Organization filtering
- [x] Customer isolation
- [x] Product isolation (N/A — not shipped)
- [x] Job isolation
- [x] Call isolation
- [x] Invoice isolation (N/A — customer invoices not shipped; SaaS Stripe scoped)
- [x] Payment isolation (N/A — customer payments not shipped; SaaS Stripe scoped)
- [x] File isolation
- [x] Audit isolation
- [x] Cross-tenant security tests

Audit: `docs/TENANT_ISOLATION_AUDIT.md`

---

## TASK 1.4.1 — Internal Service Tenant Boundary Hardening

### Description

Close the remaining Task 1.4 risk: a shared `INTERNAL_SERVICE_TOKEN` must not act as unrestricted cross-tenant authority.

Today, call-originated CRM/scheduling/knowledge/handoff paths can require `X-Call-Scope` (see `docs/CALL_AUTHORIZATION.md`). Legacy telephony `/tenants/{tenant_id}/…`, resolve, and some pre-call internals still trust path/body `tenant_id` when only the shared token is present.

### Goal

- Eliminate unrestricted `tenant_id` trust when only `INTERNAL_SERVICE_TOKEN` is supplied
- Require a stronger call- or service-scoped credential wherever tenant context matters
- Ensure internal routes cannot switch tenants by modifying path/body/query `tenant_id`
- Add cross-tenant internal-service IDOR tests
- Preserve the existing `X-Call-Scope` mechanism
- Do **not** redesign session JWT, API keys, or RBAC

### Inventory (current token-only surfaces)

Classify every `require_internal_token` route before changing behavior:

| Class | Examples | Target |
|-------|----------|--------|
| Call-originated | CRM tools, scheduling, knowledge search, handoff | Keep/require `X-Call-Scope`; body/path tenant must match claim |
| Pre-call bootstrap | `POST /internal/telephony/resolve`, inbound observed | May issue tenant-only scope; after issue, subsequent calls use that scope |
| Legacy telephony provision | `/tenants/{tenant_id}/phone-numbers/…` | Replace path-tenant trust with scoped credential or ops session; fail closed on mismatch |
| Platform bootstrap / rare admin | auth bootstrap, explicit super-admin overrides | Document + separate capability; never usable as default voice/worker auth |

### Approach (minimal)

1. Extend or reuse `CallScope` / HMAC scope family for **service scopes** where needed (e.g. `source=sip_resolve|worker|provision`), without a second tenant-context system.
2. For tenant-owned internal mutations/reads: require scope (or ops session) such that authenticated `tenant_id` is authoritative; path/body `tenant_id` is only accepted when it matches.
3. Keep `REQUIRE_CALL_SCOPE=true` as production default; tighten non-call internals that still bypass it.
4. Do not remove `INTERNAL_SERVICE_TOKEN` — treat it as transport auth only, not tenant selection.

### Checklist

- [ ] Inventory all `require_internal_token` routes and classify (call / pre-call / provision / platform)
- [ ] Call-originated routes: shared token alone cannot select arbitrary tenant
- [ ] Path/body/query `tenant_id` cannot escalate across tenants when scope is present
- [ ] Legacy `/tenants/{tenant_id}/…` telephony mutations cannot be switched by path alone
- [ ] Preserve `X-Call-Scope` issuance from resolve + call start
- [ ] Cross-tenant internal-service IDOR tests (token + wrong tenant_id → DENIED)
- [ ] Docs: update `docs/CALL_AUTHORIZATION.md` + `docs/TENANT_ISOLATION_AUDIT.md`
- [ ] No production changes in this task without staged rollout notes

### Out of scope

- New IdP / mTLS mesh / per-tenant service accounts redesign
- Postgres RLS
- Frontend auth changes
- Phase 2 onboarding

### Acceptance

```text
INTERNAL_SERVICE_TOKEN alone ≠ tenant authority
Scoped credential (or ops session) binds tenant
Cross-tenant internal IDOR tests PASS
Existing call-scope behavior intact
```

---

# PHASE 2 — BUSINESS ONBOARDING

## TASK 2.1 — Onboarding State

### Description

Create a persistent onboarding process.

### Checklist

- [x] Onboarding status
- [x] Current step
- [x] Completed steps
- [x] Progress
- [x] Resume onboarding
- [x] Skip optional steps
- [x] Save partial progress

Docs: `docs/ONBOARDING_ARCHITECTURE.md`

---

## TASK 2.2 — Business Information Wizard

### Description

Collect business information during signup.

### Steps

1. Business
2. Industry
3. Business model
4. Products/services
5. Customers
6. Scheduling
7. AI agent
8. Review

### Checklist

- [x] Business name
- [x] Industry
- [x] Country
- [x] State
- [x] Timezone
- [x] Currency
- [x] Website
- [x] Phone
- [x] Email
- [x] Business size
- [x] Business type

Docs: `docs/BUSINESS_CONFIGURATION.md`

---

## TASK 2.3 — Business Model Selection

### Description

Determine what the business sells.

### Options

- Products
- Services
- Products + Services
- Subscriptions
- Appointments
- Rentals
- Custom

### Checklist

- [x] Selection UI
- [x] Store configuration
- [x] Validation
- [x] API
- [x] Tests

---

## TASK 2.4 — Industry Templates

### Description

Create configuration templates for different industries.

### Initial templates

- HVAC
- Plumbing
- Electrical
- Cleaning
- Automotive
- Dental
- Medical
- Real Estate
- E-commerce
- Consulting
- Beauty/Salon
- Fitness
- Custom

### Checklist

- [x] Template model
- [x] Template configuration
- [x] HVAC template
- [x] Plumbing template
- [x] Electrical template
- [x] Cleaning template
- [x] E-commerce template
- [x] Generic template
- [x] Template tests

Docs: `docs/CRM_CONFIGURATION.md`

---

## TASK 2.5 — Automatic CRM Setup

### Description

When onboarding finishes, automatically create the CRM configuration based on business type and industry.

Example:

HVAC:

```text
Customers
Properties
Equipment
Services
Jobs
Appointments
Technicians
Estimates
Invoices
Payments
Memberships
```

E-commerce:

```text
Customers
Products
Categories
Inventory
Orders
Payments
Shipping
Returns
Discounts
```

### Checklist

- [x] Read onboarding configuration
- [x] Select template
- [x] Enable modules
- [x] Create default settings
- [x] Create default statuses
- [x] Create default fields
- [x] Create default workflows
- [x] Persist configuration
- [x] Make process idempotent
- [x] Add tests

---

# PHASE 3 — DYNAMIC CRM ENGINE

## TASK 3.1 — CRM Modules

### Description

CRM modules must be configurable instead of hardcoded per business.

### Modules

- Customers
- Companies
- Leads
- Deals
- Products
- Services
- Orders
- Jobs
- Appointments
- Estimates
- Invoices
- Payments
- Equipment
- Memberships
- Calls
- Conversations
- Tasks

### Checklist

- [x] Module registry
- [x] Enable/disable modules
- [x] Organization-specific configuration
- [x] Module ordering
- [x] Navigation generated dynamically
- [x] Permission mapping

Docs: `docs/CRM_MODULES.md`, `docs/DYNAMIC_CRM_ARCHITECTURE.md`

---

## TASK 3.2 — Custom Fields

### Description

Allow businesses to add custom fields without database migrations for every field.

### Field types

- Text
- Number
- Currency
- Boolean
- Date
- DateTime
- Email
- Phone
- URL
- Dropdown
- Multi-select
- Address
- File
- Relationship

### Checklist

- [x] Custom field model
- [x] Field definitions
- [x] Validation
- [x] Field rendering
- [x] API support
- [x] Search support
- [x] Filtering support
- [x] Required fields
- [x] Default values
- [x] Permission support

Docs: `docs/CUSTOM_FIELDS.md`

---

## TASK 3.3 — Custom Objects

### Description

Allow businesses to create business-specific entities.

Examples:

- Equipment
- Vehicle
- Property
- Contract
- Asset
- Membership
- Subscription

### Checklist

- [x] Object definition
- [x] Object fields
- [x] Relationships
- [x] CRUD API
- [x] Dynamic UI
- [x] Permissions
- [x] Search
- [x] Audit history

Docs: `docs/CUSTOM_OBJECTS.md`

---

## TASK 3.4 — Relationships

### Description

Support relationships between CRM entities.

Examples:

```text
Customer
 ├── Locations
 ├── Jobs
 ├── Orders
 ├── Appointments
 ├── Equipment
 ├── Invoices
 └── Calls
```

### Checklist

- [x] Relationship model
- [x] One-to-one
- [x] One-to-many
- [x] Many-to-many
- [x] Relationship API
- [x] Relationship UI
- [x] Query support

---


## TASK 3.5 — Dynamic CRM Hardening & Phase 4 Readiness

### Description

Harden Phase 3 Dynamic CRM before Phase 4 commerce.

### Checklist

- [x] Effective configuration caching + invalidation
- [x] EAV query/index hardening
- [x] Filter AST security
- [x] Relationship entity classification / integrity
- [x] Custom object & field IDOR hardening
- [x] Pagination limits
- [x] Audit coverage (record update)
- [x] Placeholder module messaging
- [x] Local performance harness
- [x] Hardening docs + staging runbook

Docs: `docs/DYNAMIC_CRM_HARDENING.md`

**Phase 4 gate:** remains `NOT READY FOR PHASE 4` until staging verification.

> **Implementation override (2026-10-06):** Tasks 4.1–4.4 Customer CRM were implemented locally under an explicit gate override. Production/staging readiness remains **BLOCKED**. See `docs/CUSTOMER_CRM.md`.

---

# PHASE 4 — CUSTOMER CRM

## TASK 4.1 — Customer

### Checklist

- [x] Customer model
- [x] Name
- [x] Phone
- [x] Email
- [x] Status
- [x] Notes
- [x] Tags
- [x] Organization
- [x] CRUD APIs
- [x] Tests

---

## TASK 4.2 — Customer Locations

### Checklist

- [x] Address
- [x] City
- [x] State
- [x] ZIP
- [x] Country
- [x] Latitude
- [x] Longitude
- [x] Access instructions
- [x] Primary location
- [x] Multiple locations

---

## TASK 4.3 — Customer Search

### Description

Allow AI and staff to quickly find customers.

### Checklist

- [x] Phone search
- [x] Email search
- [x] Name search
- [x] Address search
- [x] Fuzzy search
- [x] Normalized phone
- [x] Database indexes
- [x] Pagination

---

## TASK 4.4 — Customer Timeline

### Checklist

- [x] Calls
- [x] SMS
- [x] Emails
- [x] Leads
- [x] Jobs
- [x] Orders (omitted — domain not implemented)
- [x] Appointments
- [x] Estimates (omitted — domain not implemented)
- [x] Invoices (omitted — domain not implemented)
- [x] Payments (omitted — domain not implemented)
- [x] Notes
- [x] Activity history

---

# PHASE 5 — PRODUCT CATALOG

## TASK 5.1 — Product Model

### Description

Allow businesses to create and manage products.

### Fields

- Name
- SKU
- Description
- Category
- Brand
- Price
- Cost
- Tax
- Weight
- Status
- Images

### Checklist

- [x] Product table
- [x] CRUD
- [x] API
- [x] Validation
- [x] Search
- [x] Filtering
- [x] Pagination
- [x] Tests

Docs: `docs/PRODUCT_CATALOG.md`

> Implementation override: local only. Production readiness remains BLOCKED.

---

## TASK 5.2 — Product Categories

### Checklist

- [x] Category model
- [x] Parent category
- [x] Nested categories
- [x] Category CRUD
- [x] Product filtering

Docs: `docs/PRODUCT_CATEGORIES.md`

---

## TASK 5.3 — Product Variants

### Description

Support products with variants.

Example:

```text
T-Shirt

Color:
Black
Blue
Red

Size:
S
M
L
XL
```

### Checklist

- [x] Variant model
- [x] SKU per variant
- [x] Price per variant
- [x] Inventory per variant (transitional stock_on_hand + inventory_item_id)
- [x] Attributes
- [x] Variant API
- [x] Tests

Docs: `docs/PRODUCT_VARIANTS.md`

---

## TASK 5.4 — Product Images

### Checklist

- [x] Upload
- [x] Storage
- [x] Multiple images
- [x] Primary image
- [x] Delete image
- [x] Secure access

Docs: `docs/PRODUCT_IMAGES.md`

---

# PHASE 6 — INVENTORY

Authoritative stock: `inventory_balances` (not transitional `product_variants.stock_on_hand`).

Migrations: `0032_inventory`, `0033_inventory_outbox_worker`.

Local verification: backend suite + Postgres concurrency + inventory outbox worker + HTTP RBAC/IDOR + frontend tsc/lint/build.

Production readiness: **BLOCKED** (staging migration, multi-worker outbox, email provider, load/EXPLAIN still required).

Docs: `docs/INVENTORY_ARCHITECTURE.md`, `docs/INVENTORY_LOCATIONS.md`, `docs/INVENTORY_TRANSACTIONS.md`, `docs/INVENTORY_ALERTS.md`

## TASK 6.1 — Inventory Model

### Checklist

- [x] Stock quantity
- [x] Reserved quantity
- [x] Available quantity (derived)
- [x] Minimum stock
- [x] Location
- [x] SKU (reuse catalog / variant SKU)
- [x] Inventory status (derived IN_STOCK / LOW_STOCK / OUT_OF_STOCK)
- [x] Variant → inventory item auto-provision + idempotent backfill script

---

## TASK 6.2 — Inventory Transactions

### Description

Never directly modify stock without creating an inventory transaction.

### Transaction types

- Purchase
- Sale
- Adjustment
- Return
- Reservation
- Release

### Checklist

- [x] Transaction model
- [x] Atomic stock update (`SELECT … FOR UPDATE`)
- [x] Transaction history
- [x] Audit log
- [x] Concurrency protection (Postgres parallel tests)
- [x] Idempotency (`Idempotency-Key`)
- [x] Inventory outbox worker (claim / retry / dead_letter)
- [x] HTTP RBAC + IDOR tests
- [x] Tests

---

## TASK 6.3 — Low Stock Alerts

### Checklist

- [x] Threshold configuration (`inventory_balances.minimum_stock` + alert config)
- [x] Alert event (transition dedupe via `last_alert_status`)
- [x] Dashboard warning + `/crm/inventory?low_stock=true` URL filter
- [x] Email (via inventory outbox → `notification_outbox`; not sync in mutation TX)
- [x] SMS optional (integration boundary only: `pending_integration`)

---

# PHASE 7 — SERVICES & PRICEBOOK

## TASK 7.1 — Services

### Checklist

- [x] Service model
- [x] Category
- [x] Description
- [x] Duration
- [x] Base price
- [x] Status
- [x] CRUD
- [x] Search

---

## TASK 7.2 — Pricebook

### Checklist

- [x] Pricebook
- [x] Pricebook items
- [x] Labor
- [x] Materials
- [x] Fixed pricing
- [x] Starting price
- [x] Organization pricing
- [x] Price overrides
- [x] Effective dates

---

# PHASE 8 — LEADS

## TASK 8.1 — Lead Management

### Checklist

- [x] Lead model
- [x] Customer relation
- [x] Source
- [x] Service/product
- [x] Priority
- [x] Status
- [x] Owner
- [x] Notes
- [x] CRUD APIs

---

## TASK 8.2 — Lead Pipeline

```text
NEW
→ QUALIFIED
→ CONTACTED
→ BOOKED
→ WON
→ LOST
```

### Checklist

- [x] Status transitions
- [x] Pipeline UI
- [x] Activity tracking
- [x] Conversion tracking

---

# PHASE 9 — ORDERS

## TASK 9.1 — Order Model

### Description

Support commerce businesses and product sales.

### Checklist

- [x] Order
- [x] Customer
- [x] Line items
- [x] Product
- [x] Variant
- [x] Quantity
- [x] Price
- [x] Discount
- [x] Tax
- [x] Shipping
- [x] Total
- [x] Status

---

## TASK 9.2 — Order Lifecycle

```text
DRAFT
→ PENDING
→ CONFIRMED
→ PROCESSING
→ SHIPPED
→ DELIVERED
→ CANCELLED
→ REFUNDED
```

### Checklist

- [x] State machine
- [x] Status history
- [x] Validation
- [x] Tests

### Hardening (post-9.2)

- [x] Idempotency request fingerprint (`0038_orders_hardening`)
- [x] Inventory flags re-synced from ledger before mutation
- [x] List serialize avoids status_history N+1
- [x] PostgreSQL concurrency + EXPLAIN ANALYZE (local)
- [x] Frontend mutation busy-guard + dedicated transition APIs

Docs: `docs/ORDERS.md`, `docs/ORDER_LIFECYCLE.md`, `docs/ORDER_INVENTORY_INTEGRATION.md`

---

# PHASE 10 — JOB MANAGEMENT

## TASK 10.1 — Jobs

### Checklist

- [x] Job model
- [x] Customer
- [x] Location
- [x] Service
- [x] Description
- [x] Priority
- [x] Status
- [x] Technician
- [x] Notes
- [x] Attachments

---

## TASK 10.2 — Job Status

```text
NEW
SCHEDULED
CONFIRMED
DISPATCHED
EN_ROUTE
ARRIVED
IN_PROGRESS
COMPLETED
CANCELLED
NO_SHOW
```

### Checklist

- [x] State machine
- [x] Status history
- [x] Validation
- [x] Audit events
- [x] Tests

### Hardening (post-10.2)

- [x] Idempotency request fingerprint (`idempotency_request_hash`, migration `0040_jobs_hardening`)
- [x] Same-key / different-payload → `idempotency_conflict`
- [x] `EDITABLE_STATUSES` enforced on PATCH; status only via transition service
- [x] Assign/unassign gated by `ASSIGNABLE_STATUSES` + `FOR UPDATE` (CRM + legacy)
- [x] Attachment MIME sniff, path sanitization, size bound, orphan best-effort cleanup
- [x] Full transition matrix / cancel / NO_SHOW / completion invariants tested
- [x] PostgreSQL concurrency (numbering, transitions, assign, idempotency, NO_SHOW vs cancel)
- [x] N+1 list bound + keyset pagination tests
- [x] Representative local EXPLAIN ANALYZE (~2k jobs, multi-tenant)
- [x] Frontend `JOB_ASSIGNABLE_STATUSES` aligned with backend
- [x] Docs: `JOBS.md`, `JOB_LIFECYCLE.md`, `JOB_ASSIGNMENT.md`

---

# PHASE 11 — APPOINTMENTS & SCHEDULING

## TASK 11.1 — Business Hours

### Checklist

- [x] Working days
- [x] Opening time
- [x] Closing time
- [x] Holidays
- [x] Timezone
- [x] Emergency hours

---

## TASK 11.2 — Technician Availability

### Checklist

- [x] Working schedule
- [x] Breaks
- [x] Vacation
- [x] Days off
- [x] Skills
- [x] Service areas

---

## TASK 11.3 — Appointment

### Checklist

- [x] Appointment model
- [x] Start time
- [x] End time
- [x] Duration
- [x] Customer
- [x] Job
- [x] Technician
- [x] Status
- [x] Timezone

---

## TASK 11.4 — Availability Engine

### Description

Calculate real availability instead of relying on static calendar slots.

### Checklist

- [x] Business hours
- [x] Technician schedule
- [x] Existing appointments
- [x] Appointment duration
- [x] Skills
- [x] Service area
- [x] Emergency priority
- [x] Timezone
- [x] Double-booking prevention
- [x] Race-condition protection

### Hardening (post-11.4)

- [x] PostgreSQL exclusion + concurrent booking / adjacent / multi-tech races
- [x] Availability-then-book race (advisory vs authoritative)
- [x] Reschedule / assign / cancel-vs-reschedule / status races
- [x] Full status transition matrix
- [x] Idempotency + appointment numbering concurrency
- [x] Business hours (adjacent/overlap/overnight reject) + emergency isolation
- [x] DST spring-forward / fall-back + IANA timezone matrix
- [x] Skills / service areas / customer-job integrity
- [x] Availability + list N+1 bounds; local EXPLAIN ANALYZE evidence
- [x] HTTP RBAC + IDOR; frontend booking conflict refresh
- [ ] Staging verification
- [ ] Production verification

---

# PHASE 12 — DISPATCH

## TASK 12.1 — Technician Management

### Checklist

- [x] Technician profile (reuse `technicians`)
- [x] Skills (Phase 11)
- [x] Service categories (via service required skills)
- [x] Service areas (Phase 11)
- [x] Schedule (Phase 11)
- [x] Status (operational status model)

---

## TASK 12.2 — Dispatch Board

### Checklist

- [x] Today's jobs
- [x] Technician columns
- [x] Unassigned jobs
- [x] Assign job
- [x] Reassign job
- [x] Drag/drop
- [x] Job priority
- [x] Status
- [x] ETA (nullable + SCHEDULE/MANUAL sources)

---

## TASK 12.3 — Technician Status

```text
AVAILABLE
BUSY
EN_ROUTE
ARRIVED
ON_BREAK
OFFLINE
```

### Checklist

- [x] Status API
- [x] Status history
- [x] Real-time updates (`dispatch_events` polling)
- [x] Authorization

### Hardening (post-12.3)

- [x] Assignment eligibility + history + idempotency
- [x] PostgreSQL concurrency (assign + status)
- [x] HTTP RBAC / IDOR
- [x] Board N+1 bound
- [x] Final consolidation: legacy `/api/jobs/{id}/assign` → `DispatchAssignmentService`
- [x] Local production-scale PostgreSQL EXPLAIN (synthetic dataset)
- [ ] Staging verification
- [ ] Production verification

---

# PHASE 13 — AI TOOL LAYER

## TASK 13.1 — AI Tool Registry

### Description

Create a centralized tool system that allows AI agents to execute business operations safely.

> Implemented as **Phase 14 AI tool contracts** on the tenancy branch:
> `callbot_platform/ai_tools/*`, `POST /internal/ai/tools/{name}`, voice-agent
> `ai_business_tools.py`. See `docs/AI_TOOLS.md`.

### Checklist

- [x] Tool registry
- [x] Tool schemas
- [x] Authentication
- [x] Organization context
- [x] Authorization
- [x] Validation
- [x] Tool logging
- [x] Error handling
- [x] Tool timeout
- [x] Tool retry policy

---

## TASK 13.2 — Customer Tools

Create:

- [x] `find_customer`
- [x] `create_customer`
- [x] `update_customer`
- [x] `get_customer_history` (as `get_customer_context`)

---

## TASK 13.3 — Commerce Tools

Create:

- [x] `search_products`
- [x] `get_product`
- [x] `check_inventory`
- [x] `get_product_price`
- [x] `create_order`
- [ ] `get_order` (covered by `get_order_status` / `find_orders`)
- [x] `get_order_status`

---

## TASK 13.4 — Service Tools

Create:

- [x] `get_services` (as `search_services`)
- [x] `get_service_price`
- [ ] `get_pricebook_item` (pricebook resolution via `get_service_price`)

---

## TASK 13.5 — Scheduling Tools

Create:

- [x] `check_availability`
- [x] `get_available_slots` (same tool; advisory slots)
- [x] `create_appointment` (+ preferred `create_booking` orchestration)
- [x] `reschedule_appointment` (AppointmentService adapter)
- [x] `cancel_appointment` (AppointmentService adapter)

---

## TASK 13.6 — Job Tools

Create:

- [x] `create_job`
- [ ] `get_job`
- [ ] `update_job`
- [ ] `get_job_status`

---

## TASK 13.7 — Billing Tools

Create:

- [ ] `create_estimate` (staff EstimateService; AI has `find_estimates` / `get_estimate`)
- [ ] `send_estimate`
- [ ] `create_invoice`
- [ ] `create_payment_link`
- [ ] `get_payment_status`

---

## TASK 13.8 — Communication Tools

Create:

- [x] `send_sms`
- [ ] `send_email`
- [x] `transfer_call` (as `request_human` handoff queue / transfer initiate)
- [ ] `create_callback`

---

# PHASE 14 — AI VOICE AGENT

> **FREEZE (2026-10-07):** Application implementation is frozen.  
> AI Tool Executor, tool registry, booking orchestration, AI RBAC, confirmation,  
> idempotency, and voice tool registration must not gain new Phase 14 features.  
> Remaining work is deployment, staging, provider smoke testing, and ops verification.  
> See `docs/AI_TOOLS.md` and `docs/PRODUCTION_READINESS.md`.

```text
Phase 14 Implementation: COMPLETE
Phase 14 Hardening: COMPLETE
Local / PostgreSQL / Performance / Security verification: COMPLETE
Overall Production Readiness: BLOCKED (voice/staging/prod smokes NOT EXECUTED)
```

## TASK 14.1 — Caller Identification

### Checklist

- [x] Read caller number (call row / session)
- [x] Normalize number (platform phone utils via tools)
- [x] Search customer (`find_customer`)
- [x] Identify existing customer
- [x] Create new customer (`create_customer` + confirmation/idempotency)
- [x] Load customer context (`get_customer_context`)

---

## TASK 14.2 — AI System Prompt

### Description

Create a structured system prompt for the AI receptionist.

AI must understand:

- Business identity
- Business hours
- Services
- Products
- Pricing
- Policies
- Customer context
- Available tools
- Escalation rules

### Checklist

- [x] Business context (profile instructions)
- [x] Customer context (tool + call facts)
- [x] Tool rules
- [x] Safety rules
- [x] Confirmation rules
- [x] Escalation rules (`request_human`)
- [x] No hallucinated data (tool-backed facts)
- [x] Prompt / structural safety tests (forbidden args + prompt-boundary suite)

---

## TASK 14.3 — AI Booking

### Flow

```text
CALL
→ IDENTIFY CUSTOMER
→ UNDERSTAND REQUEST
→ FIND SERVICE
→ CHECK AVAILABILITY (advisory)
→ OFFER SLOTS
→ CONFIRM (HMAC)
→ create_booking → BookingOrchestrationService (Job + Appointment)
→ SEND SMS (queued)
```

### Checklist

- [x] New customer flow
- [x] Existing customer flow
- [x] Availability (advisory)
- [x] Slot selection
- [x] Booking confirmation (HMAC prepare→confirm)
- [x] Job + appointment via `create_booking`
- [x] SMS enqueue (`QUEUED` ≠ delivered)
- [x] Error handling (`booking_conflict`, customer-safe errors)
- [x] PostgreSQL concurrency / race verification

---

## TASK 14.4 — AI Commerce

### Example

Customer:

> "Do you have a blue iPhone 15 Pro case?"

AI:

```text
search_products()
→ get product
→ check_inventory()
→ get_product_price()
→ answer customer
```

### Checklist

- [x] Product search
- [x] Variant search
- [x] Inventory lookup
- [x] Price lookup (server-authoritative)
- [x] Product questions (tool-backed)
- [x] Order lookup / status (customer-scoped IDOR fail-closed)
- [x] Create order if enabled (`create_order` → DRAFT; inventory on Order lifecycle)
- [x] Forbidden price/inventory/status args rejected

---

## TASK 14.5 — Deployment gates (not application features)

These remain open until executed in a real environment:

- [ ] Twilio live smoke
- [ ] LiveKit live smoke
- [ ] OpenAI Realtime live smoke
- [ ] Caller identification live smoke
- [ ] Booking live smoke
- [ ] Commerce live smoke
- [ ] Order live smoke
- [ ] SMS live smoke
- [ ] Human handoff live smoke
- [ ] Staging deployment
- [ ] Staging migration verification
- [ ] Staging RBAC verification
- [ ] Staging voice smoke
- [ ] Production deployment
- [ ] Production smoke

---

# PHASE 15 — AI SMS AGENT

## TASK 15.1 — Incoming SMS

### Checklist

- [ ] Receive webhook
- [ ] Identify customer
- [ ] Load conversation
- [ ] Detect intent
- [ ] Generate response
- [ ] Execute tools
- [ ] Store message
- [ ] Store AI action

---

## TASK 15.2 — SMS Booking

### Checklist

- [ ] Check availability
- [ ] Offer slots
- [ ] Confirm
- [ ] Book
- [ ] Send confirmation

---

# PHASE 16 — KNOWLEDGE BASE / RAG

## TASK 16.1 — Knowledge Sources

Allow:

- [ ] PDF
- [ ] DOCX
- [ ] Website
- [ ] Text
- [ ] FAQs
- [ ] Policies
- [ ] Business information
- [ ] Product descriptions

---

## TASK 16.2 — Ingestion

### Checklist

- [ ] Upload
- [ ] Extract text
- [ ] Chunk
- [ ] Generate embeddings
- [ ] Store vectors
- [ ] Store metadata
- [ ] Organization isolation
- [ ] Re-index
- [ ] Delete knowledge

---

## TASK 16.3 — Retrieval

### Checklist

- [ ] Semantic search
- [ ] Organization filtering
- [ ] Metadata filtering
- [ ] Context limit
- [ ] Relevance threshold
- [ ] Retrieval logging

---

## TASK 16.4 — RAG vs Tools

Use RAG for:

- [ ] FAQs
- [ ] Policies
- [ ] General business information
- [ ] Product descriptions

Use database tools for:

- [ ] Customer information
- [ ] Inventory
- [ ] Pricing
- [ ] Availability
- [ ] Jobs
- [ ] Appointments
- [ ] Orders
- [ ] Payments

---

# PHASE 17 — ESTIMATES

> Implemented on the tenancy branch as **Phase 13 Estimates** (migration `0043_estimates`).
> Email/SMS delivery and customer portal approval remain future work.

## TASK 17.1 — Estimate

### Checklist

- [x] Estimate model
- [x] Customer
- [x] Job (via conversion)
- [x] Line items
- [x] Quantity
- [x] Unit price
- [x] Discount
- [x] Tax
- [x] Total

---

## TASK 17.2 — Estimate Workflow

```text
DRAFT
→ SENT
→ VIEWED
→ APPROVED
→ REJECTED
→ EXPIRED
→ CONVERTED
```

### Checklist

- [x] State machine
- [ ] Email
- [ ] SMS
- [x] Internal approval/rejection APIs
- [x] Convert to job
- [x] Convert to order

---

# PHASE 18 — INVOICING

## TASK 18.1 — Invoice

### Checklist

- [ ] Invoice model
- [ ] Invoice number
- [ ] Customer
- [ ] Job/order
- [ ] Line items
- [ ] Tax
- [ ] Discount
- [ ] Total
- [ ] Balance
- [ ] Due date
- [ ] Status

---

## TASK 18.2 — Invoice Workflow

```text
DRAFT
→ SENT
→ PARTIALLY_PAID
→ PAID
→ OVERDUE
→ VOID
```

---

# PHASE 19 — PAYMENTS

## TASK 19.1 — Stripe Integration

### Checklist

- [ ] Payment link
- [ ] Checkout
- [ ] Webhook
- [ ] Payment status
- [ ] Partial payment
- [ ] Refund
- [ ] Idempotency
- [ ] Audit logging

---

## TASK 19.2 — AI Payment

### Checklist

- [ ] Generate payment link
- [ ] Send SMS
- [ ] Send email
- [ ] Check payment status
- [ ] Never expose card data

---

# PHASE 20 — MEMBERSHIPS

## TASK 20.1 — Membership Plans

### Checklist

- [ ] Plan
- [ ] Monthly price
- [ ] Annual price
- [ ] Included services
- [ ] Discounts
- [ ] Priority scheduling
- [ ] Status

---

## TASK 20.2 — Customer Membership

### Checklist

- [ ] Subscribe
- [ ] Cancel
- [ ] Renew
- [ ] Upgrade
- [ ] Downgrade
- [ ] Membership history

---

# PHASE 21 — EQUIPMENT / ASSETS

## TASK 21.1 — Equipment

### Checklist

- [ ] Equipment model
- [ ] Manufacturer
- [ ] Model
- [ ] Serial number
- [ ] Installation date
- [ ] Warranty
- [ ] Customer relationship
- [ ] Location

---

## TASK 21.2 — Equipment History

### Checklist

- [ ] Service history
- [ ] Repairs
- [ ] Parts
- [ ] Technician notes
- [ ] Photos
- [ ] Warranty status

---

# PHASE 22 — AUTOMATION ENGINE

## TASK 22.1 — Event System

Events:

- [ ] CALL_COMPLETED
- [ ] LEAD_CREATED
- [ ] JOB_CREATED
- [ ] APPOINTMENT_CREATED
- [ ] APPOINTMENT_REMINDER
- [ ] TECHNICIAN_DISPATCHED
- [ ] JOB_COMPLETED
- [ ] ESTIMATE_SENT
- [ ] ESTIMATE_APPROVED
- [ ] INVOICE_CREATED
- [ ] PAYMENT_COMPLETED
- [ ] ORDER_CREATED
- [ ] ORDER_SHIPPED

---

## TASK 22.2 — Automation Actions

Actions:

- [ ] SEND_SMS
- [ ] SEND_EMAIL
- [ ] CREATE_TASK
- [ ] CREATE_JOB
- [ ] CREATE_APPOINTMENT
- [ ] SEND_PAYMENT_LINK
- [ ] REQUEST_REVIEW
- [ ] WEBHOOK

---

## TASK 22.3 — Workflow Builder

### Description

Allow business owners to visually create:

```text
WHEN
Job Completed

IF
Invoice > $500

THEN
Send SMS
+
Send Email
+
Create Follow-up Task
```

### Checklist

- [ ] Trigger model
- [ ] Conditions
- [ ] Actions
- [ ] Workflow UI
- [ ] Enable/disable
- [ ] Execution history
- [ ] Retry
- [ ] Error handling

---

# PHASE 23 — CALL INTELLIGENCE

## TASK 23.1 — Call Recording

### Checklist

- [ ] Recording reference
- [ ] Secure storage
- [ ] Retention settings
- [ ] Access permissions

---

## TASK 23.2 — Transcript

### Checklist

- [ ] Transcription
- [ ] Speaker identification
- [ ] Timestamp
- [ ] Search
- [ ] Storage

---

## TASK 23.3 — AI Summary

Generate:

- [ ] Intent
- [ ] Problem
- [ ] Outcome
- [ ] Customer sentiment
- [ ] Appointment status
- [ ] Follow-up
- [ ] Important notes

---

## TASK 23.4 — Call Classification

Categories:

- [ ] Booking
- [ ] Rescheduling
- [ ] Cancellation
- [ ] Sales
- [ ] Support
- [ ] Emergency
- [ ] Billing
- [ ] Product inquiry
- [ ] Order inquiry
- [ ] Spam
- [ ] Human transfer

---

# PHASE 24 — HUMAN HANDOFF

## TASK 24.1 — Call Transfer

### Checklist

- [ ] Transfer to user
- [ ] Transfer to department
- [ ] Transfer to technician
- [ ] Emergency routing
- [ ] Business-hours routing
- [ ] After-hours routing

---

## TASK 24.2 — Handoff Context

Before transfer provide:

- [ ] Customer
- [ ] Intent
- [ ] Summary
- [ ] Job
- [ ] Appointment
- [ ] AI actions already performed

---

# PHASE 25 — COMMUNICATION AUTOMATION

## TASK 25.1 — SMS Templates

Templates:

- [ ] Booking confirmation
- [ ] Reminder
- [ ] Technician en route
- [ ] Technician arrived
- [ ] Job completed
- [ ] Invoice
- [ ] Payment
- [ ] Review request

---

## TASK 25.2 — Email Templates

- [ ] Booking
- [ ] Estimate
- [ ] Invoice
- [ ] Receipt
- [ ] Reminder
- [ ] Review

---

# PHASE 26 — ADMIN DASHBOARD

## TASK 26.1 — Dashboard

Display:

- [ ] Calls
- [ ] Leads
- [ ] Bookings
- [ ] Jobs
- [ ] Revenue
- [ ] Outstanding invoices
- [ ] AI resolution rate

---

## TASK 26.2 — CRM UI

- [ ] Customers
- [ ] Leads
- [ ] Products
- [ ] Services
- [ ] Orders
- [ ] Jobs
- [ ] Appointments
- [ ] Calls
- [ ] Invoices

---

## TASK 26.3 — Scheduling UI

- [ ] Calendar
- [ ] Day view
- [ ] Week view
- [ ] Technician view
- [ ] Drag/drop
- [ ] Reschedule

---

## TASK 26.4 — Dispatch UI

- [ ] Technician columns
- [ ] Job cards
- [ ] Unassigned jobs
- [ ] Assignment
- [ ] Reassignment
- [ ] Status
- [ ] ETA

---

# PHASE 27 — ANALYTICS

## TASK 27.1 — Call Analytics

- [ ] Total calls
- [ ] Answer rate
- [ ] Missed calls
- [ ] Average duration
- [ ] Transfer rate
- [ ] AI resolution rate

---

## TASK 27.2 — Sales Analytics

- [ ] Leads
- [ ] Qualified leads
- [ ] Bookings
- [ ] Conversion
- [ ] Revenue per lead
- [ ] Revenue per call
- [ ] Product sales

---

## TASK 27.3 — Operations Analytics

- [ ] Jobs completed
- [ ] Cancellation rate
- [ ] No-show rate
- [ ] Technician utilization
- [ ] Average job duration
- [ ] Response time

---

# PHASE 28 — INTEGRATIONS

## TASK 28.1 — Integration Framework

Create a provider abstraction.

Example:

```text
CRMProvider
├── ServiceTitan
├── HubSpot
└── Salesforce
```

### Checklist

- [ ] Provider interface
- [ ] OAuth
- [ ] Credential storage
- [ ] Connection status
- [ ] Sync status
- [ ] Error handling
- [ ] Retry

---

## TASK 28.2 — Calendar Integrations

- [ ] Google Calendar
- [ ] Outlook Calendar

---

## TASK 28.3 — Commerce Integrations

- [ ] Shopify
- [ ] WooCommerce

---

## TASK 28.4 — Accounting

- [ ] QuickBooks
- [ ] Xero

---

# PHASE 29 — AI BUSINESS SETUP

## TASK 29.1 — AI Onboarding Assistant

### Description

Allow the owner to describe their business in natural language.

Example:

> "We are an HVAC company in Texas. We install and repair residential AC systems."

AI should suggest:

```text
Industry: HVAC

Business Model:
Products + Services

Modules:
✓ Customers
✓ Products
✓ Inventory
✓ Services
✓ Jobs
✓ Appointments
✓ Technicians
✓ Estimates
✓ Invoices
✓ Payments
✓ Equipment
✓ Memberships
✓ AI Calling
```

### Checklist

- [ ] Natural language input
- [ ] Business extraction
- [ ] Industry classification
- [ ] Business model detection
- [ ] Module recommendation
- [ ] Custom field recommendation
- [ ] Service recommendation
- [ ] AI configuration recommendation
- [ ] Human review
- [ ] Confirm setup
- [ ] Persist configuration

---

# PHASE 30 — AI AGENT CONFIGURATION

## TASK 30.1 — Agent Profile

Allow business owner to configure:

- [ ] Agent name
- [ ] Voice
- [ ] Language
- [ ] Tone
- [ ] Greeting
- [ ] Business hours
- [ ] Transfer rules
- [ ] Escalation rules

---

## TASK 30.2 — Agent Capabilities

Allow:

- [ ] Answer calls
- [ ] Book appointments
- [ ] Reschedule
- [ ] Cancel
- [ ] Product search
- [ ] Inventory lookup
- [ ] Pricing
- [ ] Lead creation
- [ ] Lead qualification
- [ ] Order lookup
- [ ] Payment links
- [ ] SMS
- [ ] Human transfer

---

# PHASE 31 — AI GUARDRAILS

## TASK 31.1 — No Hallucinated Business Data

AI must never invent:

- [ ] Price
- [ ] Inventory
- [ ] Availability
- [ ] Technician
- [ ] Customer history
- [ ] Order status
- [ ] Payment status

All operational information must come from tools.

---

## TASK 31.2 — Confirmation Rules

Require confirmation before:

- [ ] Booking
- [ ] Cancellation
- [ ] Rescheduling
- [ ] Order placement
- [ ] Payment action
- [ ] Destructive changes

---

## TASK 31.3 — Tool Authorization

Every tool call must verify:

- [ ] Organization
- [ ] User/agent permission
- [ ] Resource ownership
- [ ] Input validation
- [ ] Audit logging

---

# PHASE 32 — AI COST TRACKING

## TASK 32.1 — Usage Tracking

Track per organization:

- [ ] Voice minutes
- [ ] LLM tokens
- [ ] AI requests
- [ ] Tool calls
- [ ] SMS
- [ ] Transcription
- [ ] Storage

---

## TASK 32.2 — COGS

Calculate:

```text
Revenue
- Voice cost
- LLM cost
- SMS cost
- Transcription cost
- Storage
- Infrastructure
=
Gross Margin
```

### Checklist

- [ ] Usage records
- [ ] Cost calculation
- [ ] Organization dashboard
- [ ] Admin COGS dashboard
- [ ] Billing limits
- [ ] Alerts

---

# PHASE 33 — SECURITY

## TASK 33.1 — Security Baseline

- [ ] Tenant isolation
- [ ] RBAC
- [ ] API authorization
- [ ] Input validation
- [ ] Rate limiting
- [ ] Webhook verification
- [ ] Audit logs
- [ ] Secure file access
- [ ] Encryption
- [ ] Secrets management

---

# PHASE 34 — OBSERVABILITY

## TASK 34.1 — Logging

Track:

- [ ] API requests
- [ ] AI requests
- [ ] Tool calls
- [ ] Voice events
- [ ] Webhooks
- [ ] Payments
- [ ] Automation executions

---

## TASK 34.2 — Metrics

Track:

- [ ] API latency
- [ ] AI latency
- [ ] Tool latency
- [ ] Tool failure rate
- [ ] Booking failure rate
- [ ] Webhook failures
- [ ] Voice failures

---

# PHASE 35 — AI TESTING

## TASK 35.1 — Voice Scenarios

Test:

- [ ] New customer
- [ ] Existing customer
- [ ] Product inquiry
- [ ] Inventory inquiry
- [ ] Price inquiry
- [ ] Booking
- [ ] Rescheduling
- [ ] Cancellation
- [ ] Emergency
- [ ] No availability
- [ ] Human transfer
- [ ] Angry customer
- [ ] After-hours call

---

## TASK 35.2 — AI Evaluation

Evaluate:

- [ ] Intent accuracy
- [ ] Customer identification
- [ ] Product identification
- [ ] Service identification
- [ ] Tool selection
- [ ] Availability correctness
- [ ] Booking correctness
- [ ] Pricing correctness
- [ ] Escalation correctness

---

# PHASE 36 — END-TO-END GOLDEN FLOWS

## FLOW 1 — Service Business

```text
Customer calls
→ AI answers
→ Finds customer
→ Understands issue
→ Finds service
→ Checks availability
→ Offers slots
→ Customer confirms
→ Creates job
→ Creates appointment
→ Assigns technician
→ Sends SMS
→ Technician dispatched
→ Technician completes job
→ Estimate if required
→ Invoice
→ Payment link
→ Payment
→ Review request
```

### Checklist

- [ ] Complete flow works
- [ ] Database state correct
- [ ] Events emitted correctly
- [ ] Notifications sent
- [ ] AI transcript correct
- [ ] Customer timeline correct

---

# FLOW 2 — Commerce Business

```text
Customer calls
→ AI identifies customer
→ Searches product
→ Checks variant
→ Checks inventory
→ Gives real price
→ Customer confirms
→ Creates order
→ Payment link
→ Payment
→ Confirmation SMS
```

### Checklist

- [ ] Product search
- [ ] Variant
- [ ] Inventory
- [ ] Price
- [ ] Order
- [ ] Payment
- [ ] Notification
- [ ] Customer timeline

---

# FLOW 3 — Existing Customer Support

```text
Customer calls
→ Identify customer
→ Load history
→ Find previous order/job
→ Understand problem
→ Check warranty
→ Create support job
→ Schedule technician
→ Send confirmation
```

### Checklist

- [ ] Customer identified
- [ ] History loaded
- [ ] Warranty checked
- [ ] Job created
- [ ] Appointment created
- [ ] SMS sent

---

# PHASE 37 — PRODUCTION READINESS

## TASK 37.1 — Reliability

- [ ] Database backups
- [ ] Retry policies
- [ ] Idempotency
- [ ] Queue retry
- [ ] Dead-letter handling
- [ ] Graceful shutdown
- [ ] Health checks
- [ ] Readiness checks

---

## TASK 37.2 — Performance

- [ ] Database indexes
- [ ] Query optimization
- [ ] Pagination
- [ ] Caching
- [ ] Connection pooling
- [ ] AI context optimization
- [ ] Tool latency optimization
- [ ] Scheduling query optimization

---

## TASK 37.3 — Final QA

- [ ] Frontend build
- [ ] Backend build
- [ ] Unit tests
- [ ] Integration tests
- [ ] E2E tests
- [ ] Security tests
- [ ] Tenant isolation tests
- [ ] AI scenario tests
- [ ] Payment tests
- [ ] Webhook tests
- [ ] Production deployment test

---

# MVP RELEASE CHECKLIST

The following must be completed before the first serious production release:

## Foundation

- [x] Multi-tenancy
- [x] Organization-managed RBAC
- [x] Platform-defined permissions
- [x] System roles
- [x] Custom organization roles
- [x] Role assignments
- [x] Permission scopes
- [x] Legacy auth migrated to permissions (1.3.1)
- [x] Fail-closed scoped authorization (1.3.2)
- [x] RBAC reconciliation + frontend permission migration (1.3.3)
- [x] AI/tool authorization
- [x] RBAC audit logs
- [ ] Tenant isolation
- [ ] Business onboarding

## CRM

- [ ] Customers
- [ ] Locations
- [ ] Leads
- [ ] Timeline
- [ ] Custom fields

## Commerce

- [ ] Products
- [ ] Categories
- [ ] Variants
- [ ] Inventory
- [ ] Orders

## Field Service

- [ ] Services
- [ ] Pricebook
- [ ] Jobs
- [ ] Appointments
- [ ] Scheduling
- [ ] Technicians
- [ ] Dispatch

## AI

- [ ] Voice agent
- [ ] AI tools
- [ ] AI booking
- [ ] Product search
- [ ] Inventory lookup
- [ ] RAG
- [ ] AI summaries
- [ ] Human handoff

## Billing

- [ ] Estimates
- [ ] Invoices
- [ ] Stripe payments

## Communication

- [ ] SMS
- [ ] Email
- [ ] Automated notifications

## Platform

- [ ] Dashboard
- [ ] Analytics
- [ ] Automation
- [ ] Audit logs
- [ ] Usage tracking
- [ ] COGS
- [ ] Monitoring

---

# IMPORTANT IMPLEMENTATION PRINCIPLE

Do NOT build this as one giant CRM.

Build it as a configurable platform:

```text
                         ORGANIZATION
                              │
                    BUSINESS CONFIGURATION
                              │
                 ┌────────────┴────────────┐
                 │                         │
            CRM CONFIG                  AI CONFIG
                 │                         │
        ┌────────┼────────┐        ┌───────┼────────┐
        │        │        │        │       │        │
     Products Services  Jobs     Voice   SMS     RAG
        │        │        │        │       │        │
        └────────┴────────┴────────┴───────┴────────┘
                              │
                       BUSINESS OS
```

Every organization should get its own:

- CRM configuration
- Modules
- Custom fields
- Custom objects
- Products
- Services
- Pricebook
- Workflows
- AI agent
- Knowledge base
- Automation
- Integrations
- Permissions

The goal is that a business owner can sign up and configure the platform without engineering changes.

---

# FINAL DEFINITION OF DONE

The platform is considered complete when a new business can:

- [ ] Sign up
- [ ] Describe their business
- [ ] Select industry
- [ ] Select business model
- [ ] Automatically receive recommended CRM configuration
- [ ] Review configuration
- [ ] Add products
- [ ] Add services
- [ ] Configure pricing
- [ ] Configure inventory
- [ ] Configure business hours
- [ ] Configure technicians
- [ ] Configure AI agent
- [ ] Upload knowledge
- [ ] Connect phone number
- [ ] Receive a customer call
- [ ] AI identifies customer
- [ ] AI understands request
- [ ] AI searches products/services
- [ ] AI checks real inventory
- [ ] AI checks real availability
- [ ] AI books appointment/order
- [ ] AI sends SMS
- [ ] Staff sees activity in CRM
- [ ] Staff manages job/order
- [ ] Technician completes job where applicable
- [ ] Estimate/invoice is generated
- [ ] Customer pays
- [ ] Automation follows up
- [ ] Business owner sees analytics

The final experience should feel like:

**"Connect your business → configure it once → AI runs the repetitive customer and operational work."**
# AI Tool Layer (Phase 14)

Typed, small-output, tenant-derived tools for the voice agent and SMS agent.

**Status:** Implementation and local verification complete; deployment verification pending.  
**Phase freeze:** AI Tool Executor, tool registry, booking orchestration, AI RBAC, confirmation, idempotency, and voice tool registration are frozen. No additional Phase 14 application features.  
**Phase 15:** SMS channel adapter reuses this layer unchanged — see `docs/AI_SMS_AGENT.md`.

---

## Architecture

```text
Caller / SMS customer
  → Voice Agent  OR  SMS Agent
  → AI Model / RuleBasedSmsBrain
  → LiveKit function_tool  OR  SmsToolBridge
  → AIToolExecutor (shared)
  → Authorization (AI tool group + domain RBAC)
  → Existing domain service
  → PostgreSQL
```

### What AI cannot do

The model and tool arguments must never:

| Capability | Enforcement |
| ---------- | ----------- |
| Access repositories directly | Handlers call domain services only |
| Execute SQL | No SQL/ORM exposed to the model |
| Choose tenant | Server-derived from call-scope / trusted body (dev only) |
| Choose permissions / role | Forbidden args + RBAC from AI Agent system role |
| Control authoritative prices | Forbidden args; OrderService/PricingService compute totals |
| Control inventory balances | Forbidden args; InventoryService / order transitions |
| Control lifecycle status | Forbidden args (`orderStatus`, `appointmentStatus`, etc.) |
| Bypass confirmation | HMAC prepare→confirm required for mutations |
| Bypass idempotency | Mutations require `operation_id`; store/replay on success |

---

## Trusted context (`AIToolContext`)

Resolved only from call-scope, call row, or session — never from free-form model “identity” fields:

| Field | Source |
| ----- | ------ |
| `tenant_id` | Call-scope (required when `REQUIRE_CALL_SCOPE=true`) |
| `call_id` | Call-scope |
| `customer_id` | Call row or session-identified customer |
| `caller_phone` | Call row |
| `actor_type` | Always `AI_VOICE_AGENT` |
| `operation_id` | Voice session (stable across retries) |
| `confirmed` | Request flag + verified HMAC token |

---

## Results (`AIToolResult`)

Structured success/error envelope:

- `ok`, `data` / `error.code`
- `error.retryable`, `error.customerSafe`
- No stack traces, SQL, or credentials in responses
- Customer-facing copy lives in `CUSTOMER_SAFE_MESSAGES` (policy)

---

## Tool registry

Each registered tool declares:

- name, description, args schema (Pydantic, `extra=forbid`)
- tool group + permission keys
- mutation / confirmation / idempotency flags
- timeout class

Unknown tools → `not_found`. Malformed/forbidden/oversized args → `invalid_arguments`.

---

## Timeout classes

| Class | Seconds | Examples |
| ----- | ------: | -------- |
| FAST_READ | 2 | find_customer, get_service_price |
| STANDARD_READ | 4 | search_*, get_customer_context |
| AVAILABILITY | 6 | check_availability |
| MUTATION | 8 | create_*, update_*, reschedule, cancel |
| EXTERNAL_PROVIDER | 10 | send_sms, request_human |

On PostgreSQL, `SET LOCAL statement_timeout` is applied. Timeouts map to `system_unavailable` (retryable, customer-safe).

---

## Retry policy

Voice HTTP client (`PlatformAiToolsClient`):

- **Reads:** up to 2 attempts on transient failures
- **Mutations:** up to 2 attempts **only with the same `operation_id`**
- Never retry: `permission_denied`, `invalid_arguments`, `not_found`, `confirmation_required`, `idempotency_conflict`, `booking_conflict`, `expired`, etc.

---

## Confirmation (HMAC)

```text
prepare (confirmed=false)
  → confirmation_required + confirmationToken
  → verbal confirm with caller
  → confirm (confirmed=true + token + same args + same operation_id)
  → mutation
```

`confirmed=true` alone is **insufficient**. The token is HMAC-bound to:

- tenant_id
- call_id
- tool name
- operation_id
- args fingerprint

Tampered args, wrong operation, missing token, or expired token → `confirmation_required` or `expired`.

### Known limitation

HMAC confirmation proves the prepare/confirm flow is cryptographically valid. It does **not** independently prove that the spoken confirmation was produced by the human caller. Do not claim audio-level authentication.

---

## Idempotency semantics (operators)

**Scope:** `tenant_id + tool + operation_id`

This is intentionally **not call-scoped**.

| Scenario | Behavior |
| -------- | -------- |
| Same tenant, tool, operation_id, same args | Replay stored result (no second mutation) |
| Same tenant, tool, operation_id, different args | `idempotency_conflict` |
| Call A then Call B, same tenant/tool/operation_id | Same logical operation (Call B replays) |
| Tenant A then Tenant B, same operation_id string | Isolated — no replay or data leak |

Storage: `telephony_idempotency_keys` with `operation=ai_tool:{tool}` and `key=operation_id`.

On PostgreSQL, concurrent same-tenant/tool/operation_id callers are serialized with `pg_advisory_xact_lock` before lookup/mutate.

---

## RBAC

- AI tool group permission (e.g. `ai.tools_crm`) plus domain permissions (`jobs.create`, `products.read`, …)
- Authorization reads the tenant **AI Agent** system role
- Permission set is cached per session for performance; **role/permission updates call `invalidate_tenant`**, which clears the AI permission cache so revocations take effect on subsequent checks

---

## Forbidden arguments

Rejected before schema parse when present in tool args (non-exhaustive): `tenantId`, `organizationId`, `permissions`, `role`, `unitPrice`, `total`, `inventoryBalance`, `appointmentStatus`, `orderStatus`, `jobStatus`, actor identity fields, etc.

---

## Booking authority

Preferred voice booking tool: **`create_booking`**.

```text
AI
  → create_booking
  → BookingOrchestrationService
      ├── Customer validation
      ├── Job creation
      ├── Appointment creation
      ├── conflict protection (exclusion / domain errors)
      ├── transaction rollback on conflict (no orphan Job)
      ├── audit
      └── notification outbox (where applicable)
```

| Tool | Role |
| ---- | ---- |
| `check_availability` | **Advisory** — slots may disappear |
| `create_booking` | **Authoritative** — final mutation |

A successful availability response never guarantees a later booking. `booking_conflict` is an expected recovery path: refresh availability and offer alternatives; never claim the original slot was booked after a conflict.

---

## Order semantics

`create_order` creates a **DRAFT** order via `OrderService`.

Inventory reservation/consumption authority remains on the appropriate Order lifecycle transition (e.g. confirm), not on the AI draft create.

AI does **not** control:

- unit price, subtotal, tax, discount, total
- inventory balances
- order status

Server-computed prices and `OrderService` remain authoritative.

Order lookup (`find_orders` / `get_order_status`) requires an identified caller customer. Cross-customer / cross-tenant lookups return indistinguishable `not_found`.

---

## SMS

Destination phone is resolved from `customerId` only. Status is **`QUEUED`** on enqueue — never report delivery when only queueing succeeded.

---

## Audit

Successful and failed tool invocations write `ai_tool.{tool_name}` audit events (resource ids include call/operation/ok/error; no secrets in payload summary).

---

## LiveKit / voice registration

When CRM or scheduling tools are enabled on the agent profile:

1. Register Phase 14 `build_ai_business_tools` (executor-backed)
2. Register legacy CRM **compat only**: `get_call_context`, `create_lead`
3. Do **not** register conflicting legacy customer upsert/lookup tools
4. Do **not** register legacy scheduling `AppointmentRepository` mutation tools

Rule: **no duplicate authoritative mutation path** for Phase 14 booking/customer operations.

Docs reference: [LiveKit function tools](https://docs.livekit.io/agents/logic/tools/definition/).

---

## Legacy HTTP surfaces

`/internal/crm` and `/internal/scheduling` may remain for non-voice clients when properly authenticated and authorized.

Phase 14 production concern is voice **registration**, not wholesale deletion of internal HTTP:

- Voice agent does not register conflicting legacy scheduling tools when Phase 14 is enabled
- Remaining internal endpoints are not a Phase 14 blocker by themselves if call-scope / internal token / RBAC remain enforced

Lead create remains on legacy `/internal/crm/leads` (tenant + AI CRM permission + idempotency).

---

## Production configuration (no secrets)

Required / expected for production voice AI:

| Setting | Notes |
| ------- | ----- |
| `REQUIRE_CALL_SCOPE=true` | Mandatory in production |
| `INTERNAL_SERVICE_TOKEN` | Voice → platform internal AI routes |
| `METADATA_HMAC_SECRET` | Call-scope + confirmation HMAC |
| AI Agent system role | Synced permissions for CRM, scheduling, products, orders, SMS, handoff |
| LiveKit | URL, API key/secret, agent dispatch |
| OpenAI | Realtime / inference credentials |
| Twilio | Telephony / SIP as deployed |
| SMS provider | Outbox worker delivery config |

Never commit or log secret values.

---

## Local PostgreSQL performance (synthetic)

**Label: LOCAL POSTGRESQL** — not production performance.

Dataset used:

```text
4 tenants
10,000 customers
1,000 products/variants   ← product-scale limitation
2,000 appointments
2,000 jobs
```

| Operation        | p50 ms | p95 ms |
| ---------------- | -----: | -----: |
| find_customer    |   2.03 |  11.49 |
| customer_context |   7.18 |  22.01 |
| service_search   |   1.10 |   4.08 |
| availability     |   3.61 |  11.57 |
| product_search   | 105.15 | 126.79 |
| inventory        |   1.28 |   5.09 |
| price            |   3.07 |   4.37 |
| order_lookup     |   0.80 |   0.96 |
| booking          |  15.77 |  31.31 |
| order_creation   |   9.63 |  22.83 |

### Product search — known optimization candidate

- Tool p95 ≈ **127 ms**
- SQL `EXPLAIN (ANALYZE)` execution ≈ **0.031 ms**
- Evidence indicates most latency is in the application/ORM path, not SQL execution
- Status: **Known optimization candidate** (not a production incident)
- Do not add indexes solely from this local p95

### Dataset / EXPLAIN limitations

- Product performance validated at **1,000** products/variants (not 10k product-scale)
- Estimate lookup EXPLAIN: **NOT EXECUTED**

### Bounded query counts (N+1 probe)

| Operation | Queries | Assessment |
| --------- | ------: | ---------- |
| get_customer_context | 17 | Intentional bounded fan-out (customer + limited jobs/appts/orders/estimates + auth) — not per-row N+1 at limit=5 |
| search_products | 7 | Bounded |
| find_orders | 5 | Bounded |
| check_availability | 13 | Bounded |

---

## HTTP API

- `GET /internal/ai/tools`
- `POST /internal/ai/tools/{tool_name}`

Headers: `X-Internal-Token`, `X-Call-Scope` (production: `REQUIRE_CALL_SCOPE=true`).

---

## Verification status

| Environment | Status |
| ----------- | ------ |
| Local pytest (`tests/test_ai_tools.py`) | VERIFIED |
| PostgreSQL concurrency (`tests/test_ai_tools_pg_concurrency.py`) | VERIFIED |
| PostgreSQL performance / EXPLAIN / N+1 (`tests/test_ai_tools_pg_perf.py`) | VERIFIED (local) |
| Voice registration unit tests | VERIFIED |
| Staging voice / Twilio / LiveKit / OpenAI / SMS | NOT EXECUTED |
| Production | NOT EXECUTED |

---

## Phase freeze

Frozen for Phase 14:

- AI Tool Executor
- Tool registry
- Booking orchestration
- AI RBAC
- Confirmation / HMAC
- Idempotency
- Voice tool registration

Future work (invoices, payments, subscriptions, advanced estimate workflows) belongs to a later phase — not Phase 14 feature development.

SMS channel specifics (webhooks, conversations, outbound outbox, loop prevention) are documented in `docs/AI_SMS_AGENT.md` and must not fork domain logic.

Phase 16 adds `search_knowledge` (tool group `knowledge`) via `KnowledgeRetrievalService`. RAG answers informational FAQs/policies only — inventory, pricing, appointments, and orders remain domain tools. See `docs/KNOWLEDGE_BASE.md`.

# AI Guardrails (Phase 31)

Production guardrails for Call & Flow voice/SMS AI. The AI is an orchestrator — not a source of truth, not an authorization authority, and not allowed to mutate the database directly.

## Freeze status

```text
APPLICATION COMPLETE / GUARDRAILS VERIFIED / LIVE VOICE VERIFICATION BLOCKED / PRODUCTION BLOCKED
```

Phase 31 is **frozen**. Do not mark provider-verified. Do not add another guardrail architecture.

Next meaningful activity is **staging/provider verification** of a real conversation path (invented inventory/price → lookup/refuse; booking/payment without confirmation → reject; disabled capability → `capability_disabled`; cross-tenant resource → reject; duplicate confirmed op → idempotent; tool unavailable → no fabricated answer).

Pre-existing unrelated ESLint `no-explicit-any` in `web/src/app/crm/handoffs/[id]/page.tsx` is **not** a Phase 31 blocker.

## Architecture flow

```text
AI Request
   ↓
Tenant Context (server-derived)
   ↓
Agent Capability (Phase 30)
   ↓
RBAC
   ↓
Resource Ownership
   ↓
Input Validation
   ↓
Confirmation (Phase 14 HMAC)
   ↓
Idempotency (operation_id)
   ↓
Phase 14 Tool Executor
   ↓
Domain Service
   ↓
Audit
   ↓
Authoritative Result
   ↓
AI Response
```

Phase 31 does **not** create a second tool executor, confirmation system, or authorization path. It catalogs authoritative data, documents confirmation classes, tightens forbidden argument injection, strengthens prompts, and adds regression tests atop Phase 14 + Phase 30.

## 1. Authoritative business data policy

These categories must come from authorized tools/domain services only:

| Category | Example tools |
| --- | --- |
| PRICE | `get_product_price`, `get_service_price`, `search_products` |
| INVENTORY | `check_inventory` |
| AVAILABILITY | `check_availability`, booking tools (result only) |
| TECHNICIAN | `check_availability`, booking/dispatch results |
| CUSTOMER_HISTORY | `get_customer_context`, `find_customer` |
| ORDER_STATUS | `find_orders`, `get_order_status` |
| PAYMENT_STATUS | `get_payment_status` |

Registry: `callbot_platform.ai_guardrails.authoritative.AuthoritativeData`.

The LLM may explain or summarize tool results. It must not invent prices, stock counts, availability, technician assignment, customer history, order status, or payment status.

## 2. Tool provenance

- Tool success payloads are the source of truth for operational facts.
- Model-generated fields such as `price`, `inventory`, `paymentStatus`, `orderStatus`, `technicianName` are rejected as tool arguments (`FORBIDDEN_ARG_KEYS` ∪ `AUTHORITATIVE_INJECTION_KEYS`).
- Provenance helper: `classify_operational_claim` — fail closed to `UNKNOWN` when tools fail.

## 3. Confirmation-required operations

Source of truth: `ToolSpec.confirmation_required` in Phase 14 `TOOL_SPECS`.

Classification registry (docs/UI): `ConfirmationOperation` in `ai_guardrails.confirmation_ops`.

At minimum, confirmation is required for:

- Booking (`create_booking`, `create_appointment`)
- Cancellation (`cancel_appointment`)
- Reschedule (`reschedule_appointment`)
- Order placement (`create_order`)
- Payment actions (`create_payment_link`, `send_payment_link_*`)
- Destructive / sensitive mutations (membership cancel, customer create/update, SMS, jobs)

HMAC tokens bind tenant, call, tool, operation_id, args fingerprint, expiry, and single-use semantics via Phase 14.

## 4. Authorization flow

Every tool invocation (Phase 14 executor):

1. Unknown tool → reject  
2. Forbidden / injection keys → reject  
3. Pydantic validation → reject  
4. Phase 30 capability (when active profile exists) → reject if disabled  
5. Confirmation (when required) → issue token or verify HMAC  
6. Idempotency lookup / xact lock  
7. RBAC `check_ai_tool` + `require_ai_permission`  
8. Handler (tenant-scoped domain services)  
9. Audit  

## 5. Tenant isolation

- `tenant_id` is taken only from trusted execution context (call-scope / session / worker).
- Model-supplied `tenant_id` / `organizationId` is forbidden.
- Domain repos filter by server `tenant_id`.

## 6. Resource ownership

Handlers use tenant-scoped services. Cross-tenant IDs fail closed (`not_found` / `tenant_access_denied` / permission errors). Never `SELECT WHERE id = model_id` without tenant scope.

## 7. Input validation

Strict Pydantic models (`StrictModel`) per tool. Invalid enums, negative quantities, unexpected fields, and forbidden keys are rejected before domain mutation.

## 8. Payment safeguards

- No raw card data in tools or prompts.
- Payment status only via `get_payment_status`.
- Payment link / send tools require confirmation + RBAC + capability `PAYMENT_LINK`.
- Amounts/status come from payment/invoice domain — not model injection (`currency`, `total`, `paymentStatus` forbidden as args).

## 9. Destructive-operation safeguards

Destructive tools (`cancel_*`, membership cancel, etc.) require confirmation and capability gates. Prefer existing soft-delete / domain-safe paths.

## 10. Audit logging

Phase 14 executor audit records tenant, actor, tool, operation_id, success/failure, mutation flag, safe metadata. Secrets, card data, and full prompts are not logged.

## 11. Fail-closed behavior

Missing tenant context, capability, RBAC, ownership certainty, invalid input, missing/expired/replayed confirmation, unknown tool, or unavailable authoritative tools → reject or “information unavailable.” Never silent unsafe downgrade.

## 12. Phase 14 relationship

Phase 14 `AIToolExecutor` remains the sole execution/security boundary for AI tools (HMAC, idempotency, RBAC, timeouts, audit).

## 13. Phase 30 relationship

Agent capabilities are an additional gate. Enabling a capability does **not** bypass RBAC, confirmation, or ownership. Catalog note exposed to admin UI.

## 14. Testing strategy

- `platform/tests/test_ai_guardrails.py` — authoritative injection, confirmation coverage/binding/expiry, capability fail-closed, catalog, provenance
- `platform/tests/test_ai_tools.py` — Phase 14 regression (HMAC, idempotency, IDOR, forbidden args)
- `platform/tests/test_agent_config.py` — Phase 30 capability enforcement
- `voice-agent/tests/test_prompt.py` — anti-hallucination prompt rules

## 15. Known provider / live-runtime limitations

Application-level guardrails and tool/domain integration are covered by automated tests (executor/domain paths — not mocked security decisions).

Live verification of OpenAI Realtime, LiveKit rooms, and Twilio telephony for guardrail behavior requires staging credentials and is **not** claimed here.

```text
Application guardrails: GUARDRAILS VERIFIED (pytest)
Tool/domain integration: Phase 14 handlers (regression covered)
OpenAI Realtime: NOT EXECUTED — LIVE VOICE VERIFICATION BLOCKED
LiveKit: NOT EXECUTED — LIVE VOICE VERIFICATION BLOCKED
Twilio: NOT EXECUTED — LIVE VOICE VERIFICATION BLOCKED
Overall: APPLICATION COMPLETE / GUARDRAILS VERIFIED / LIVE VOICE VERIFICATION BLOCKED / PRODUCTION BLOCKED
```

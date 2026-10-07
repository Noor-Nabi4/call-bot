# AI SMS Agent (Phase 15)

Channel adapter for inbound/outbound SMS on top of frozen Phase 14 `AIToolExecutor`.

**Status:** Implementation and local verification complete; provider and staging verification pending.  
**Production gate:** `PRODUCTION BLOCKED` until real Twilio + staging smoke passes.

```text
Implementation complete
Local verification complete
Provider verification pending
Staging verification pending
Production verification pending
```

Phase 14 remains frozen. SMS does **not** duplicate authorization, confirmation, HMAC, idempotency, RBAC, booking orchestration, or domain services.

---

## Architecture

```text
Incoming SMS
    ↓
POST /webhooks/twilio/sms/inbound
    ↓
Twilio signature + E.164 normalize
    ↓
Tenant resolve (TenantPhoneNumber.e164 = To)
    ↓
Customer identify (CustomerService.lookup_by_phone)
    ↓
sms_conversations / sms_messages (idempotent MessageSid)
    ↓
SmsAgentOrchestrator (RuleBasedSmsBrain → SmsToolBridge)
    ↓
AIToolExecutor (Phase 14)
    ↓
Domain services → PostgreSQL
    ↓
Customer-safe reply → NotificationOutbox → Twilio
```

Voice and SMS converge at `AIToolExecutor` → domain services → PostgreSQL.

---

## Webhook security

| Control | Behavior |
| -------- | -------- |
| Signature | `X-Twilio-Signature` via `twilio.request_validator.RequestValidator` |
| Auth token | Tenant subaccount token (encrypted) or `TWILIO_AUTH_TOKEN` |
| Tenant | From trusted `tenant_phone_numbers.e164` only — never from SMS body |
| Customer | Server `lookup_by_phone` — model cannot select arbitrary customer |
| Malformed | Missing To/From/MessageSid → 400 |
| Invalid signature / unknown To | 403 |

Status callbacks: `POST /webhooks/twilio/sms/status` (same signature + tenant resolve).

---

## Inbound idempotency

- Unique `(tenant_id, provider_message_id)` on `sms_messages`
- Fast-path select before AI
- Concurrent inserts: PostgreSQL unique + `BEGIN NESTED` / IntegrityError
- Status lifecycle: `RECEIVED` → `PROCESSING` → `PROCESSED` | `FAILED`
- Duplicate webhook → 200 + empty TwiML; **no** second AI/tools/outbound

Correctness is PostgreSQL-backed; Redis is not required.

---

## Customer identification

Reuses Phase 14 / CRM:

```text
Normalize E.164 → lookup_by_phone → EXACT | NONE | AMBIGUOUS
```

- Unknown number → controlled reply (no auto-create unless future policy uses `create_customer` via executor)
- Ambiguous → clarification / handoff path
- AI never chooses `tenant_id` / `customer_id`

---

## Conversation model

Migration: `0044_sms_agent`

- `sms_conversations` — tenant + customer phone + business phone, `workflow_state` JSON
- `sms_messages` — inbound/outbound, provider SID, status, optional `outbox_id`

Context window: latest **20** messages (configurable constant), tenant-scoped. No audit secrets or credentials in AI context.

Directions: `INBOUND` | `OUTBOUND`  
Outbound statuses: `QUEUED` → `SENT` (provider accepted) → `DELIVERED` / `FAILED` (status callback). Queued ≠ delivered.

---

## AI orchestration

- `RuleBasedSmsBrain` — structured intents for tests/offline (`BOOKING`, `AVAILABILITY`, `ORDER_STATUS`, …)
- Intent routes orchestration only; mutations still require Phase 14 confirmation + `operation_id`
- `SmsToolBridge` allowlists SMS tools and calls `AIToolExecutor` only
- Confirmation YES/NO bound to conversation `workflow_state` (`confirmation_token`, `operation_id`, booking args)

System rules: concise SMS, no fabricated availability/prices/inventory, mutations need explicit confirmation.

---

## Booking (SMS)

```text
BOOKING intent → search_services → check_availability → offer 1..3 slots
→ customer selects → revalidate availability → create_booking (prepare)
→ YES → create_booking (confirm) → confirmation SMS via outbox
```

- Availability is advisory; booking revalidates
- Uses `create_booking` only (no SMS-local job/appointment APIs)
- Booking success is independent of SMS delivery (outbox retries; no booking rollback)

---

## Outbound SMS

- Destination = server conversation `phone_e164` only
- `SmsOutboundService` → `NotificationService.enqueue_sms` (idempotency key)
- Outbox worker sets `provider_ref` and syncs `sms_messages` to `SENT`
- Loop prevention: ignore inbound webhooks whose MessageSid matches known outbound SID / outbox `provider_ref`

---

## Observability (structured log events)

```text
sms.webhook.received | sms.webhook.duplicate
sms.customer.identified
sms.ai.started | sms.ai.completed | sms.ai.failed
sms.tool.executed
sms.outbound.queued | sms.outbound.sent | sms.outbound.delivered | sms.outbound.failed
sms.booking.started | sms.booking.completed | sms.booking.failed
```

Correlate with `tenant_id`, `conversation_id`, `message_id`, `operation_id`. No provider secrets or raw stack traces in customer replies.

---

## Operational runbook

1. Map Twilio number → `tenant_phone_numbers`
2. Configure inbound URL: `https://<api>/webhooks/twilio/sms/inbound`
3. Configure status URL: `https://<api>/webhooks/twilio/sms/status`
4. Ensure `TWILIO_AUTH_TOKEN` or tenant subaccount encrypted token + `METADATA_HMAC_SECRET`
5. Run notification outbox worker
6. Apply Alembic head `0044_sms_agent`

### Staging smoke

1. Send real SMS to mapped DID  
2. Confirm signature accept, customer match, AI reply queued  
3. Duplicate webhook → single inbound + single outbound  
4. Booking path with YES confirmation  
5. Confirm outbox send + optional delivery callback  

### Production rollout

Do not mark ready until staging smoke and provider verification pass. See `docs/PRODUCTION_READINESS.md`.

---

## Verification status

| Check | Status |
| ----- | ------ |
| Local unit/integration (SQLite) | VERIFIED (`tests/test_sms_agent.py` — 16 passed) |
| Local PostgreSQL concurrency | VERIFIED (`test_concurrent_duplicate_webhook`) |
| Local PostgreSQL booking E2E | VERIFIED (`test_sms_booking_end_to_end_pg`) |
| Local PostgreSQL perf / EXPLAIN | VERIFIED (local): inbound webhook p50 ≈ 7.55 ms, p95 ≈ 8.27 ms; dataset 4 tenants / ~10k customers / 10016 messages / 1001 conversations; context query uses `ix_sms_messages_tenant_conversation_created` (execution ≈ 0.019 ms) |
| Twilio live inbound/outbound | NOT EXECUTED / PROVIDER VERIFICATION BLOCKED |
| Staging E2E | NOT EXECUTED |
| Production | NOT EXECUTED |

# Call Authorization

**Date:** 2026-10-06 (Phase 2)

## Problem

A shared `INTERNAL_SERVICE_TOKEN` alone allowed any caller with the token to pass an arbitrary `tenant_id` on internal CRM APIs.

## Mechanism

HMAC call-scope tokens (same secret family as LiveKit metadata: `METADATA_HMAC_SECRET`).

Header:

```text
X-Internal-Token: <shared service token>
X-Call-Scope: {"v":1,"tenant_id":"...","call_id":"...","iat":...,"exp":...,"sig":"..."}
```

Issued by:

- `POST /internal/telephony/resolve` → tenant-only scope (`call_id` null)
- `POST /internal/crm/calls/start` → call-bound scope in response field `call_scope`

## Enforcement

| Setting | Behavior |
|---------|----------|
| `REQUIRE_CALL_SCOPE=false` | Legacy: internal token only (tests / migration) |
| `REQUIRE_CALL_SCOPE=true` | Missing/invalid/expired/tampered scope → 401; body tenant/call mismatch → 403 |

Production startup (`require_production_settings`) **requires** `REQUIRE_CALL_SCOPE=true`.

`call/end` with scope enforces:

1. Scope signature + expiry
2. `call_id` exists and belongs to scoped `tenant_id`
3. Body `tenant_id` / `call_id` match the claim

## What is still token-only (pre-call / ops)

- SIP resolve / inbound observed (pre-call; issues tenant scope)
- Legacy telephony provisioning under `/tenants/...` (internal-token gated; not call-originated)
- Agent profile fetch at worker startup (pre-call)
- Ops session cookie APIs

## Voice agent

All call-originated platform clients (`PlatformCrmClient`, `PlatformSchedulingClient`, `PlatformKnowledgeClient`, `PlatformHandoffClient`) send `X-Call-Scope` after resolve/start. Agent wires the same scope token into every client.

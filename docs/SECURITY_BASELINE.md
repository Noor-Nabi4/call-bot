# Security Baseline (Phase 33)

Application security model for Call & Flow. This document describes **existing**
controls made authoritative and testable — not a second RBAC, audit, encryption,
or rate-limit stack.

## Frozen status

```text
PHASE 33 — SECURITY

APPLICATION COMPLETE
SECURITY BASELINE VERIFIED
LIVE SECURITY VERIFICATION BLOCKED
PRODUCTION BLOCKED
```

Do **not** interpret local pytest as penetration testing, SOC 2, ISO 27001, or PCI compliance.
The four limitations below are **deployment / staging drill items**, not evidence that
application Phase 33 is incomplete.

---

## Authentication model

| Item | Implementation |
|------|----------------|
| Mechanism | Session JWT (HS256) in HttpOnly cookie and/or `Authorization: Bearer` |
| Password hashing | bcrypt (`security/session.py`) |
| Cookie flags | `HttpOnly`, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true` |
| Resolution | `api/deps.require_tenant_user` → DB user check → `TenantContext` |
| Bootstrap | `POST /auth/bootstrap` — internal token only |
| Public auth | `POST /auth/signup`, `POST /auth/login` (rate-limited) |

**CSRF:** Cookie-authenticated SPA mutations rely on `SameSite=Lax` + CORS allowlist.
There is **no** separate CSRF token layer. OAuth uses single-use state (`OAuthStateService`).

**Status:** APPLICATION VERIFIED (unit/HTTP tests). STAGING / LIVE: NOT VERIFIED.

---

## Tenant isolation model

```text
Authenticated principal
        ↓
TenantContext (session | API key | call-scope | worker job row)
        ↓
Repository/service requires tenant_id
        ↓
WHERE tenant_id = :tenant_id
```

Never trust client-supplied `tenant_id` / `organization_id` as authority.
Call-scope HMAC binds voice tools to a tenant+call (`security/call_scope.py`).

Postgres RLS is **not** enabled; isolation is application-layer.

**Status:** APPLICATION VERIFIED (existing isolation/IDOR suites + Phase 33 baseline).
Staging drills: NOT EXECUTED.

---

## RBAC model

Authoritative catalog: `rbac/catalog.py` + `AuthorizationService`.

Route gates: `require_permission` / `require_entitled_permission`.

Legacy JWT role strings are **not** authorization authority (see `docs/RBAC_LEGACY_AUTH_AUDIT.md`).

UI-hidden controls are not security boundaries.

**Status:** APPLICATION VERIFIED (HTTP RBAC matrices across CRM domains).

---

## API authorization classes

| Class | Examples | Gate |
|-------|----------|------|
| PUBLIC | `/health`, `/liveness`, `/readiness`, `/auth/login`, `/auth/signup`, `/billing/plans` | None / auth rate limit where noted |
| AUTHENTICATED | `/auth/me` | Session |
| TENANT-SCOPED | CRM, billing, agents, usage-cost summary | Session + RBAC + tenant |
| ADMIN (org) | `/api/admin/*` with entitled permissions | Session + permission |
| INTERNAL | Fleet COGS, telephony provisioning, agent-profile fetch | `X-Internal-Token` (constant-time compare) |
| WEBHOOK | Stripe, Twilio SMS | Provider signature verification |
| CALL-SCOPE | `/internal/*/…` voice tools | Internal token + call-scope HMAC |

**Public health surfaces (keep minimal):**

- `/health` → `{"status":"ok"}` only (no DB/provider/config)
- `/liveness` → `{"status":"alive"}` only (process up; no dependency checks)
- `/readiness` → orchestration probe: `ok`/`fail` checks for postgres + object-storage class; **no** SQL/driver error strings or secret material

---

## Rate limiting

Reuse `security/rate_limit.SlidingWindowRateLimiter` (in-process):

| Surface | Limit |
|---------|-------|
| Auth login | 20 / minute / IP+tenant+email |
| Auth signup | 10 / hour / IP+slug+email |
| Agent settings mutations | 20 / minute / actor |
| Public API keys (`/v1`) | 120 / minute / key |

**Multi-instance:** in-process limiters do **not** coordinate across replicas.
Production should also apply edge/WAF rate limits. There is no Redis-backed
limiter in this codebase today — do not pretend distributed limiting exists.

**Status:** APPLICATION VERIFIED for unit + login HTTP threshold. Edge limiting: NOT VERIFIED.

---

## Webhook verification

| Provider | Verification | Notes |
|----------|--------------|-------|
| Stripe (billing) | Stripe signature construct | Reject invalid |
| Stripe (CRM payments) | Stripe signature construct | Reject invalid |
| Twilio SMS | Twilio request signature + tenant auth token | Tenant from DID, not body trust |
| Integrations HMAC helper | `integrations/webhooks.verify_hmac_sha256` | Library; ingest idempotent |

Replay/idempotency: provider event IDs / outbox / ledger idempotency keys.

**Status:** APPLICATION VERIFIED (existing provider signature tests). LIVE: NOT VERIFIED.

---

## Audit logging

`telephony.audit.write_audit` → `TelephonyAuditEvent` (tenant, actor, action, resource ids, summary).

Do not store passwords, API keys, OAuth tokens, Stripe secrets, or card data.
Integration HTTP logging uses `redact_headers`.

**Status:** APPLICATION VERIFIED (mutation audit patterns). Full SIEM: NOT VERIFIED.

---

## Secure file access

- Tenant-prefixed keys: `tenants/{tenant_id}/…` (S3) or `{root}/{tenant_id}/…` (filesystem)
- `sanitize_object_key` rejects `..`, encoded traversal, null bytes, absolute paths
- MIME allowlist + max upload bytes
- Downloads via short-lived signed/presigned URLs after RBAC

**Status:** APPLICATION VERIFIED (traversal + isolation tests). LIVE object store: NOT VERIFIED.

---

## Encryption

Phase 28 `CredentialCipher` (Fernet) via `CREDENTIALS_ENCRYPTION_KEY`.

Encrypts: OAuth tokens, Twilio subaccount auth tokens, integration API keys.

Never return decrypted credentials from APIs.

**Status:** APPLICATION VERIFIED (round-trip + redaction tests). Key rotation drill: NOT EXECUTED.

---

## Secrets management

- Secrets from environment / secret manager — not source code
- Frontend may only use `NEXT_PUBLIC_*` non-secret config (API URL, site URL)
- Server-only: `METADATA_HMAC_SECRET`, Stripe/Twilio/OpenAI/LiveKit secrets, `SESSION_SECRET`, `CREDENTIALS_ENCRYPTION_KEY`
- Test fixtures use obvious fake values

If a real secret appears in git history, treat as a credential-rotation incident (out of band).

**Status:** APPLICATION VERIFIED (repo scan of app code — no live secrets found). History rotation: N/A unless discovered.

---

## CORS & security headers

### Platform API

- CORS allowlist from `OPS_CORS_ORIGINS` + production HTTPS web origins (`origins.py`)
- Credentials allowed only for listed origins (never `*` with credentials)
- `SecurityHeadersMiddleware`: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, tight API CSP; HSTS in production
- Production: `TrustedHostMiddleware` for `api.callandflow.com`

### Next.js (`web/next.config.ts`)

Browser security headers including a CSP compatible with Next.js / LiveKit (`unsafe-inline` / `unsafe-eval` currently required).

**Status:** APPLICATION VERIFIED (header + CORS unit tests). Staging CSP browser drill: NOT EXECUTED.

---

## AI security boundaries (Phases 14 / 30 / 31)

```text
tenant → RBAC → capability → ownership → validation → confirmation → idempotency → mutation → audit
```

AI tools must not bypass tenant isolation, RBAC, or confirmation gates.

**Status:** APPLICATION VERIFIED via existing Phase 14/30/31 test suites (regression required).

---

## Billing / COGS security (Phase 32)

- Usage ledger ingest is server-side only (call completion, tools, SMS, storage snapshot)
- Org APIs are read-oriented (`/api/admin/usage-cost/summary|alerts`) with `billing.read`
- Fleet rollup (`/usage-cost/fleet`) requires internal token — not tenant session
- Clients cannot POST usage quantity, unit cost, pricing snapshot, revenue, or margin
- Corrections use controlled adjustment entries (immutable history)

**Status:** APPLICATION VERIFIED (Phase 32 + Phase 33 billing isolation tests).

---

## Background jobs

Workers derive tenant from the claimed job/outbox row before touching tenant data.
Do not trust free-form tenant IDs in payloads without that binding.

**Status:** APPLICATION VERIFIED (existing worker/telephony patterns). LIVE: NOT VERIFIED.

---

## Verification legend

| Label | Meaning |
|-------|---------|
| APPLICATION VERIFIED | Covered by automated tests / code audit in this repo |
| STAGING VERIFIED | Exercised against staging infrastructure |
| LIVE PROVIDER VERIFIED | Exercised against live Twilio/Stripe/etc. |
| NOT VERIFIED / NOT EXECUTED / BLOCKED | Evidence missing |

---

## Known limitations (keep visible)

These are legitimate remaining risks. Do **not** “fix” them by inventing parallel
security architecture in application code; revisit during staging/live drills.

1. **No PostgreSQL RLS** — application-level tenant filtering is the primary isolation mechanism. A missed repository filter remains an IDOR risk.
2. **Rate limiting is not distributed** — in-process limits will not protect consistently across multiple API replicas. Edge/WAF limiting must be part of deployment.
3. **No CSRF token layer** — `SameSite=Lax + CORS` is a mitigation, not equivalent to a dedicated CSRF defense.
4. **CSP allows `unsafe-inline` / `unsafe-eval`** — currently required for Next.js / LiveKit web compatibility; keep explicit and tighten only with browser verification.

Also: staging/live provider security drills not executed; no SOC 2 / ISO 27001 / PCI claims.

# Integrations (Phase 28)

Production-grade provider abstraction for connecting external systems without coupling Call & Flow CRM/business logic to vendors.

## Verification status (2026-10-08)

| Layer | Status |
| --- | --- |
| Framework / application | **APPLICATION COMPLETE** |
| Framework unit/contract/security tests | **PASS** (20 tests in `tests/test_integrations.py`) |
| Migration `0054_integrations` (isolated) | **PASS** (upgrade / downgrade / re-upgrade) |
| Full Alembic chain from empty DB | **BLOCKED** — pre-existing failure in `0024_organization_rbac` (`tenants.business_size` missing mid-chain). Unrelated; not modified. |
| Live/sandbox provider API verification | **BLOCKED — CREDENTIALS UNAVAILABLE** for all nine providers |
| Production readiness | **PRODUCTION BLOCKED** |

### Platform OAuth / credential config (presence only)

| Provider | Config |
| --- | --- |
| Google Calendar | NOT CONFIGURED |
| Outlook Calendar | NOT CONFIGURED |
| HubSpot | NOT CONFIGURED |
| Salesforce | NOT CONFIGURED |
| Shopify | NOT CONFIGURED |
| QuickBooks | NOT CONFIGURED |
| Xero | NOT CONFIGURED |
| ServiceTitan | NOT CONFIGURED (tenant API keys; no fixtures) |
| WooCommerce | NOT CONFIGURED (tenant API keys; no fixtures) |
| `CREDENTIALS_ENCRYPTION_KEY` | CONFIGURED |

## Architecture

```text
Call & Flow Core
       │
Provider Interfaces (protocols + DTOs)
       │
Provider Registry / Adapters
       │
┌──────┼──────┬──────────┐
CRM  Calendar Commerce Accounting
```

Core code depends only on:

- `IntegrationProvider` protocol
- Normalized DTOs (`ExternalCustomer`, `ExternalAppointment`, …)
- `IntegrationService` / `SyncEngine` / `WebhookIngestService`

Provider-specific HTTP, OAuth quirks, and schemas live under `callbot_platform/integrations/providers/`.

## Supported providers

| Category   | Provider         | Auth        | Live verify | Production ready |
| ---------- | ---------------- | ----------- | ----------- | ---------------- |
| CRM        | ServiceTitan     | API key     | BLOCKED     | No |
| CRM        | HubSpot          | OAuth       | BLOCKED     | No |
| CRM        | Salesforce       | OAuth       | BLOCKED     | No |
| Calendar   | Google Calendar  | OAuth       | BLOCKED     | No |
| Calendar   | Outlook / Graph  | OAuth       | BLOCKED     | No |
| Commerce   | Shopify          | OAuth       | BLOCKED     | No |
| Commerce   | WooCommerce      | API keys    | BLOCKED     | No |
| Accounting | QuickBooks       | OAuth       | BLOCKED     | No |
| Accounting | Xero             | OAuth       | BLOCKED     | No |

**Honesty gate:** framework + adapters are implemented. Do not treat any provider as production-ready without PASS live/sandbox verification.

## Capabilities

Each provider declares a capability set (e.g. `CUSTOMERS_READ`, `APPOINTMENTS_WRITE`, `WEBHOOKS`). Unsupported operations raise `UNSUPPORTED_OPERATION`.

## OAuth

1. `POST /api/admin/integrations/{provider}/connect` — creates/updates connection (`CONNECTING`), stores single-use OAuth state (tenant + user + provider bound, TTL 10 minutes), returns `authorization_url`.
2. Provider redirects to frontend callback with `code` + `state`.
3. `POST /api/admin/integrations/{provider}/callback` — consumes state (CSRF / replay / tenant swap prevented), exchanges code at provider token URL, encrypts tokens, sets `CONNECTED`.

If token exchange fails or is unavailable, status is `ERROR` / `REAUTH_REQUIRED` — never fake `Connected` without tokens.

Token refresh: `refresh_access_token` + `IntegrationService.refresh_credentials` + async job `integration.oauth_refresh`. Prior refresh token is retained when the provider omits a rotated value; credentials are upserted in one write.

### Platform env (OAuth apps)

```text
INTEGRATIONS_GOOGLE_CLIENT_ID / INTEGRATIONS_GOOGLE_CLIENT_SECRET
INTEGRATIONS_MICROSOFT_CLIENT_ID / INTEGRATIONS_MICROSOFT_CLIENT_SECRET
INTEGRATIONS_HUBSPOT_CLIENT_ID / INTEGRATIONS_HUBSPOT_CLIENT_SECRET
INTEGRATIONS_SALESFORCE_CLIENT_ID / INTEGRATIONS_SALESFORCE_CLIENT_SECRET
INTEGRATIONS_SHOPIFY_CLIENT_ID / INTEGRATIONS_SHOPIFY_CLIENT_SECRET
INTEGRATIONS_QUICKBOOKS_CLIENT_ID / INTEGRATIONS_QUICKBOOKS_CLIENT_SECRET
INTEGRATIONS_XERO_CLIENT_ID / INTEGRATIONS_XERO_CLIENT_SECRET
INTEGRATIONS_OAUTH_REDIRECT_BASE
CREDENTIALS_ENCRYPTION_KEY
```

Never commit client secrets. UI shows **Not configured** when app credentials are missing.

### API-key providers

- **WooCommerce:** store URL + consumer key/secret via `POST .../api-key` (encrypted).
- **ServiceTitan:** client credentials / tenant id via `POST .../api-key` (encrypted). Not OAuth.

## Credential security

- Table `integration_credentials` stores Fernet-encrypted access/refresh tokens and extra blobs.
- API responses only include `has_access_token` / `has_refresh_token` metadata.
- Tokens are never logged; Authorization headers are redacted in HTTP helpers.

## Sync model

- `POST /api/admin/integrations/{id}/sync` enqueues `integration.sync` async job and returns `sync_run` + `async_job_id`.
- `SyncEngine` pages via `provider.sync_page`, persists cursors, creates/updates `integration_external_mappings` for idempotency.
- Domain CRM upsert (customer/appointment/order rows) remains provider-specific and is **not** live-verified without sandbox credentials.
- Directions: `IMPORT` | `EXPORT` | `BIDIRECTIONAL` (explicit per connection).
- Conflict default: detect + log (`MAPPING_CONFLICT`); do not silently overwrite domain entities until provider-specific upsert is verified.

## Webhooks

- `WebhookIngestService` verifies tenant+integration ownership, hashes payload, dedupes on `(tenant_id, integration_id, provider_event_id)`.
- Signature helpers: HMAC-SHA256 (`verify_hmac_sha256`).
- Tenant context comes from the trusted integration row — not arbitrary payload fields.

## External ID mapping

`integration_external_mappings` uniquely maps `(tenant, integration, entity_type, external_id)` ↔ internal UUID. Email alone is never the universal identity key.

## Retry / rate limits

`integrations/http.py` classifies 429/5xx as retryable with exponential backoff + jitter, honors `Retry-After`, and does not retry auth/permission/invalid request errors.

## Connection status

`DISCONNECTED` · `CONNECTING` · `CONNECTED` · `SYNCING` · `SYNCED` · `ERROR` · `REAUTH_REQUIRED` · `DISABLED`

## RBAC

```text
integrations.read | connect | update | delete | sync
```

Tenant scope always from authenticated session — never from client-supplied `tenant_id`.

## Audit

Uses existing `write_audit` / telephony audit events:

- `integration_connect_started`
- `integration_connected`
- `integration_disconnected`
- `integration_sync_requested`
- `integration_oauth_exchange_failed` / `_blocked`
- `integration_oauth_refreshed` / `integration_oauth_refresh_failed`
- `integration_webhook_received`

## Admin UI

`/settings/integrations` — category cards, status, capabilities, Connect / Sync / Reconnect / Disconnect (with confirmation). OAuth callback: `/settings/integrations/callback`.

## Operational troubleshooting

| Symptom                         | Check                                              |
| ------------------------------- | -------------------------------------------------- |
| Not configured                  | Platform OAuth env vars for that provider          |
| ERROR after OAuth               | Token exchange logs (no secrets); redirect URI match |
| REAUTH_REQUIRED                 | Refresh token revoked; reconnect                   |
| Sync queued but no records      | Live API credentials / sandbox; adapter probe      |
| 403 on APIs                     | RBAC permission + entitled subscription            |
| Full `alembic upgrade head` fails mid-chain | Pre-existing `0024_organization_rbac` / Tenant model drift — document separately |

## Provider verification matrix

Use only: `PASS` | `BLOCKED` | `FAIL` | `NOT EXECUTED` | `N/A`.

Until sandboxes are available, every provider cell for Auth/Read/Write/Sync live API is **BLOCKED**.

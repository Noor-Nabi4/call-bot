# AI Cost Tracking (Phase 32)

Financial/usage accounting layer over existing operational events. Reuses Phase 14 tool audit, call `billable_seconds`, `call_cogs`, SaaS plans, NotificationOutbox/SMS, and object storage metadata. Does **not** create a second billing or notification system.

## Freeze / gate

```text
APPLICATION COMPLETE / USAGE + COGS VERIFIED / LIVE PROVIDER VERIFICATION BLOCKED / PRODUCTION BLOCKED
```

Do not claim live OpenAI / LiveKit / Twilio / Stripe invoice COGS verification without provider execution.

## Accounting model

```text
Observed Usage
      ↓
Usage Ledger
      ↓
Pricing Snapshot
      ↓
Calculated Cost
      ↓
Revenue Source
      ↓
COGS
      ↓
Gross Margin
```

### Provenance labels (`AccountingProvenance`)

| Label | Meaning |
| --- | --- |
| **Actual** (`ACTUAL_PROVIDER`) | Backed by authoritative provider/billing records |
| **Internal** (`ACTUAL_INTERNAL`) | Authoritative application measurement (e.g. call wall-clock) |
| **Configured** (`CONFIGURED_RATE`) | Calculated using configured pricing/rates × verified quantity |
| **Estimated** (`ESTIMATED`) | Derived but not yet provider/invoice verified |
| **Allocated** (`ALLOCATED_COST`) | Internal infrastructure allocation |
| **Unavailable** (`UNAVAILABLE`) | No trustworthy value exists |

Configured OpenAI rates applied to provider token counts are **configured cost on actual usage**, never “actual provider invoice cost”.

### Revenue separation

| Field | Provenance | Notes |
| --- | --- | --- |
| `actual_revenue_*` | Actual / Unavailable | Finalized Stripe invoice/payment only (not stored yet → Unavailable) |
| `configured_subscription_revenue_*` | Configured | Plan catalog `unit_amount` |
| `estimated_overage_revenue_*` | Estimated | In-app overage; **not** Stripe invoiced |

**Stripe metered overage is not considered actual revenue until Stripe invoicing/metering confirms it.**

Billing lifecycle for billable usage: `UNBILLED` → `ESTIMATED` → `INVOICED` → `PAID` (plus `VOIDED` / `ADJUSTED`). Usage detected ≠ usage billed ≠ usage paid.

### Gross margin

- **Actual gross margin** — only when actual revenue and actual provider costs both exist (`verified: true`).
- **Calculated gross margin** — configured subscription revenue minus configured/allocated/actual-provider COGS.
- Estimated overage is **excluded** from calculated margin.
- Missing infrastructure is **Unavailable**, never coerced to `$0`.

## Architecture flow

```text
Operational Event
      ↓
Usage Event
      ↓
Idempotency
      ↓
Pricing Resolver
      ↓
Cost Snapshot
      ↓
Usage Ledger
      ↓
Aggregations (provenance-aware)
      ↓
Organization Dashboard (/settings/cogs)
      ↓
Admin COGS Fleet (X-Internal-Token)
```

Future Stripe metering boundary (`StripeMeteringGateway`):

```text
usage ledger entry
    ↓
billable usage
    ↓
Stripe meter/event
    ↓
Stripe invoice
    ↓
actual revenue
```

Currently `NOT_WIRED` — no live meter sends.

## 1. Usage categories

| Category | Unit | Usage provenance | Cost provenance |
| --- | --- | --- | --- |
| VOICE_MINUTES | ceil minutes | ACTUAL_INTERNAL | CONFIGURED_RATE |
| LLM_*_TOKENS | tokens | ACTUAL_PROVIDER (when payload present) | CONFIGURED_RATE |
| AI_REQUESTS | requests | ACTUAL_INTERNAL | UNAVAILABLE |
| TOOL_CALLS | calls | ACTUAL_INTERNAL | UNAVAILABLE |
| SMS | messages | ACTUAL_PROVIDER (SENT/DELIVERED) | CONFIGURED_RATE |
| TRANSCRIPTION | seconds | ACTUAL_PROVIDER (only if duration present) | CONFIGURED_RATE |
| STORAGE | bytes | ACTUAL_INTERNAL snapshot | CONFIGURED_RATE or UNAVAILABLE |
| INFRASTRUCTURE | period | ALLOCATED_COST or omitted | ALLOCATED_COST or UNAVAILABLE |

## 2–4. Lifecycle, idempotency, provider refs

Unchanged from Phase 32: unique `(tenant_id, idempotency_key)`; snapshots in `meta_json.pricing_snapshot`; integer micros.

Historical corrections use `entry_kind=adjustment` rows — originals are never overwritten.

## Migrations

- `0055_usage_ledger` — ledger + alert dedupe
- `0056_usage_ledger_provenance` — `usage_provenance`, `billing_status`, `entry_kind`

## APIs

- `GET /api/admin/usage-cost/summary` — org usage/COGS/revenue/margin with provenance
- `GET /api/admin/usage-cost/alerts` — soft voice limits
- `GET /api/admin/usage-cost/fleet` — internal token; no estimated→actual revenue aggregation

## Known provider verification limitations

| Layer | Status |
| --- | --- |
| Application usage ledger | VERIFIED (pytest) |
| Live OpenAI / LiveKit / Twilio | NOT EXECUTED |
| Live storage billing | NOT EXECUTED |
| Stripe invoice actual revenue | NOT EXECUTED / UNAVAILABLE in API |
| Stripe metered overage | NOT WIRED |

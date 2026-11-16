# Pricebook Pricing

Authoritative resolution: `PricingService.resolve_service_price`.

## Pricing types

| Type | Amount fields |
|------|----------------|
| `FIXED` | `price` |
| `STARTING_AT` | `starting_price` (or `price`) |
| `HOURLY` | `hourly_rate` (or `price`) |
| `CUSTOM_QUOTE` | amounts optional |

Money uses `Decimal` / PostgreSQL `NUMERIC` only — never float for persisted amounts.

## Precedence

```text
1. Active organization/tenant override (pricebook + service, effective at time)
2. Active pricebook item (same scope)
3. Service.base_price → source=service_base
4. No amount → source=no_price
```

Sources in API payloads: `organization_override` | `pricebook_item` | `service_base` | `no_price`.

This platform treats **tenant = organization**. Overrides live in `pricebook_overrides` (no separate org hierarchy). Customer-specific pricing is deferred.

When multiple candidates theoretically match (should not after overlap rules), selection is deterministic: `effective_from DESC NULLS LAST`, then `id DESC`.

## Fallback (deliberate)

When the pricebook item is missing, inactive, archived, or not effective at `at`:

- Use `service.base_price` if present (`service_base`)
- Else return `no_price` with `price=null` (typical for `CUSTOM_QUOTE`)

Historical rows are never overwritten; create a new effective-dated item/override.

Inactive/archived services and archived/inactive pricebooks do not participate in normal resolution (`not_found` / inactive errors).

## Effective dates

Semantics: **inclusive** `[effective_from, effective_until]`.

- `NULL` bound = unbounded (−∞ / +∞)
- `at == effective_until` is still effective
- `effective_until` must not precede `effective_from`
- Adjacent non-touching ranges are allowed, e.g. `[2027-01-01, 2027-06-30]` and `[2027-07-01, 2027-12-31]`
- Ranges that share an instant overlap and are rejected

## Overlap protection

Scope: active (`status=ACTIVE`, `archived_at IS NULL`) rows for the same:

```text
tenant_id + pricebook_id + service_id
```

(applies to both `pricebook_items` and `pricebook_overrides`)

Mechanisms:

1. Application: lock parent `pricebooks` row (`FOR UPDATE`), lock peer rows for the scope, reject overlaps (`effective_overlap`)
2. PostgreSQL (migration `0035_services_pricebook_hardening`): `EXCLUDE USING gist` on inclusive `tstzrange` (requires `btree_gist`)

Default pricebook: at most one active default per tenant (partial unique index + tenant-wide `FOR UPDATE` when flipping defaults).

## AI / voice

Future tools must call this resolver — never invent prices via LLM.

Hot path targets indexed filters on tenant + pricebook + service + effective window (no full catalog scan).

## Staging verification

**STATUS = NOT EXECUTED** — Production readiness **BLOCKED**.

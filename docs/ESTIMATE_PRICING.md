# Estimate Pricing

## Resolution

| Item type | Price source |
|-----------|--------------|
| SERVICE | Existing `ServicesPricebookService.resolve_price` (override → pricebook item → service base) |
| PRODUCT | Variant price else product price (Order catalog convention) |
| CUSTOM | Explicit `unit_price` (requires `estimates.update`) |

Optional `unit_price` on SERVICE/PRODUCT is stored as a snapshot with `pricing_source_snapshot=manual_override`.

## Snapshots

Each line stores:

- name / description / SKU or code
- unit price
- tax rate (products)
- pricing source

Later catalog price changes do **not** mutate existing estimates.

## Tax

Minimal model: product `tax_rate` percent applied to taxable amount after line discount (same helper as Orders). Not a jurisdiction tax engine.

# Product Variants

Optional variants with attribute combinations and SKU/price overrides.

## Model

`product_variants` + `product_attributes` / `product_attribute_values` / `product_variant_attribute_values`.

## Behavior

- Variant SKU required; registered in `catalog_skus`
- `attribute_fingerprint` = sorted value UUIDs joined by `|` — unique per active product
- Effective price: variant.price if set, else product.price (same for cost)
- `stock_on_hand` transitional; prefer future `inventory_item_id`

## APIs

```text
GET/POST /api/admin/crm/products/{id}/variants
GET/PATCH/DELETE .../variants/{variant_id}
POST /api/admin/crm/products/{id}/attributes
```

# Product Catalog

Phase 5 Tasks 5.1–5.4 implement a first-class transactional Product Catalog.

> **Implementation-gate override:** Built locally under the same development override as Customer CRM. Staging and production readiness remain **BLOCKED** (`docs/PRODUCTION_READINESS.md`).

## Architecture

```text
Tenant
  ├── product_brands
  ├── product_categories (nested via parent_id)
  ├── catalog_skus (tenant-wide SKU registry)
  └── products
        ├── product_attributes / product_attribute_values
        ├── product_variants (+ variant attribute links)
        └── product_images (object-storage metadata)
```

Products are **not** Dynamic CRM Custom Objects. `PRODUCTS` is a `PLATFORM_ENTITY`.

## Money & currency

- `price` / `cost`: `Numeric(19, 4)`, non-negative
- `tax_rate`: percent `0–100` (`Numeric(8, 4)`) — product-level only, not a tax engine
- Currency comes from `tenants.currency` (ISO 4217)

## SKU

`catalog_skus` enforces **tenant-scoped** uniqueness across products and variants. Matching is case-insensitive (`sku_normalized`).

## Inventory boundary

`product_variants.stock_on_hand` is **transitional**. Future Inventory owns stock via `inventory_item_id`. No stock ledger/warehouses in Phase 5.

## RBAC

`products.read` / `create` / `update` / `delete` cover products, categories, variants, and images. Cost fields require `products.update`.

## Audit

`write_audit` → `telephony_audit_events`.

## Migration

`0031_product_catalog` after `0030_customer_crm`.

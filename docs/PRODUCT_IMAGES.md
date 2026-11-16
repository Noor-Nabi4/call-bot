# Product Images

Image binaries live in object storage; PostgreSQL stores metadata only.

## Model

`product_images`: `object_key`, content_type, file_size, dimensions, alt_text, sort_order, is_primary, optional `variant_id`.

## Storage

Reuses `get_object_storage()` (filesystem / S3 / R2 / MinIO). Keys:

```text
products/{product_id}/images/{uuid}.{ext}
```

Allowed MIME: `image/jpeg`, `image/png`, `image/webp`, `image/gif` (also added to global allow-list). Magic-byte sniffing rejects spoofed types.

## Security

- Tenant-scoped metadata + storage paths
- RBAC `products.update` / `delete`
- Private objects; download via signed URL / storage URL TTL
- At most one primary image per product scope and per variant scope

## APIs

```text
GET/POST /api/admin/crm/products/{id}/images
POST     .../images/{image_id}/primary
DELETE   .../images/{image_id}
```

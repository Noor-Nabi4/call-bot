# Custom Objects (Task 3.3)

```text
organization_custom_object_definitions
        ↓
organization_custom_object_records
        ↓
crm_custom_field_values
```

No per-tenant DDL. Soft-archive definitions and records.

## APIs

```text
GET/POST/PATCH/DELETE /api/admin/crm/objects
GET/POST              /api/admin/crm/objects/{id}/fields
GET/POST/PATCH/DELETE /api/admin/crm/objects/{id}/records
POST                  /api/admin/crm/objects/{id}/records/search
```

Permissions: `custom_objects.read`, `custom_objects.manage`.

UI: `/crm/objects/[id]` with metadata-driven `DynamicForm` / `FieldRenderer`.

# Custom Fields (Task 3.2)

Definitions: extended `organization_crm_fields`  
Values: `crm_custom_field_values` (typed columns)

## Ownership

```text
owner_scope = module | object
owner_key   = MODULE_KEY | object_key
UNIQUE (tenant_id, owner_scope, owner_key, field_key)
```

## Types

TEXT, NUMBER, CURRENCY, BOOLEAN, DATE, DATETIME, EMAIL, PHONE, URL, DROPDOWN, MULTI_SELECT, ADDRESS, FILE, RELATIONSHIP

Defaults and required flags are enforced server-side. Disabling a field does not invalidate historical values.

## APIs

```text
GET/POST   /api/admin/crm/modules/{module}/fields
PATCH/DELETE /api/admin/crm/modules/{module}/fields/{id}
```

Filter/search uses a controlled AST (`field`, `operator`, `value`) translated to parameterized SQL.

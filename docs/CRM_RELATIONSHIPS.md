# CRM Relationships (Task 3.4)

```text
organization_crm_relationship_definitions
organization_crm_relationship_links
```

Cardinality: `ONE_TO_ONE` | `ONE_TO_MANY` | `MANY_TO_MANY`.

Definitions are configuration; links are instances. Cross-tenant links are impossible (tenant_id on every row + session scope).

## APIs

```text
GET/POST/PATCH/DELETE /api/admin/crm/relationships
GET  /api/admin/crm/{entity_type}/{entity_key}/{id}/relationships
POST /api/admin/crm/{entity_type}/{entity_key}/{id}/relationships/{key}
DELETE …/{key}/{target_id}
```

Disabled definitions reject new links. Soft-disable preserves existing edges.

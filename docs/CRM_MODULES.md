# CRM Modules (Task 3.1)

Platform registry: `callbot_platform.business_config.modules`.

Organization state: `organization_crm_modules` (`enabled`, `display_order`, `source`).

## APIs

| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/admin/crm/modules` | `organization.read` |
| PATCH | `/api/admin/crm/modules/{key}` | `crm.configure` |
| PUT | `/api/admin/crm/modules/order` | `crm.configure` |
| GET | `/api/admin/crm/configuration` | `organization.read` |

Required modules (`CUSTOMERS`, `CALLS`) cannot be disabled.

Navigation is generated from enabled modules + permission keys — not a hardcoded React list.

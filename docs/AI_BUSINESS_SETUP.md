# AI Business Setup

Phase 29 — natural-language business onboarding with human confirmation.

> **AI recommendations never directly mutate tenant configuration. Owner confirmation is required.**

## Flow

```text
Describe → Analyze → (optional clarifications ≤3) → Review/Edit → Confirm → Domain persist
```

1. Owner describes the business in free text.
2. Platform builds a structured recommendation (heuristics always; OpenAI optional refine).
3. If ambiguous, up to three clarification questions may be asked.
4. Owner reviews modules, services, custom fields, product categories, and AI setup.
5. Only `POST /api/admin/business-setup/confirm` persists through existing domain services.

Analyze and draft endpoints store **onboarding draft state only** (`OrganizationOnboarding.state_data.ai_business_setup`). They do not create CRM modules, services, or products.

## APIs

| Method | Path | Permission | Purpose |
|--------|------|------------|---------|
| `GET` | `/api/admin/business-setup` | `business_setup.read` | Current draft/confirm state |
| `POST` | `/api/admin/business-setup/analyze` | `business_setup.generate` | Generate recommendation |
| `PUT` | `/api/admin/business-setup/recommendation` | `business_setup.update` | Save owner-edited draft |
| `POST` | `/api/admin/business-setup/confirm` | `business_setup.confirm` | Apply via domain services |

All endpoints are authenticated, tenant-scoped from the session (never from model output), and RBAC-protected.

## Extraction schema

Validated Pydantic models in `callbot_platform.ai_business_setup.schemas`:

- `business_profile` — industry, models, flags (field service, appointments, memberships, inventory, equipment)
- `modules` — keys from canonical `CRM_MODULES` / `MODULE_KEYS`
- `custom_fields` — label + field_key + entity module (recommendation only until confirm)
- `services` — name/description; **price always unset**
- `product_categories` — category names only (no SKUs/inventory)
- `ai_configuration` — purpose, tone, greeting, capabilities; risky actions listed as disabled
- `clarifications` — max 3 questions

## Recommendation logic

1. **Heuristics** (`heuristics.py`) classify industry via keyword taxonomy aligned to `business_config.industries`, detect business models from `business_config.models_catalog`, and seed modules from `crm_templates` for the industry/model pair.
2. **Optional OpenAI** (`llm.py`) may refine when `OPENAI_API_KEY` is set. The business description is sent only as untrusted user content inside a JSON payload. System instructions forbid following prompt-injection text.
3. **Validation** (`validate.py`) rejects unknown industries (`INVALID_INDUSTRY`), modules (`INVALID_MODULE`), and malformed payloads (`AI_CONFIGURATION_INVALID`).
4. Provider failures fall back to heuristics rather than blocking onboarding when a usable baseline exists.

## Persistence (confirm)

On confirm, `AiBusinessSetupService` applies:

1. `OrganizationService.update` — industry + primary business model
2. `CrmSetupService.setup_from_recommendation` — template statuses/workflows + selected modules/fields
3. `ServiceCatalog.create` — selected services with `base_price=None` (idempotent by name)
4. Onboarding state — stores AI config recommendation blob; marks related steps complete when allowed

Uses a single DB session transaction (`get_db` commit/rollback). Failures roll back the request; success writes `AI_BUSINESS_SETUP_CONFIRMED`.

Confirm is **idempotent** on `(tenant_id, operation_id)` — repeated confirms return the prior result without duplicating services/modules.

## Security

- Tenant isolation: all state keyed by server-derived `tenant_id`
- Model cannot choose tenant/org/database IDs
- No credentials, customers, invoices, or payment data sent to the model
- Prompt injection: description treated as data, not instructions
- Risky AI tools (refunds, payments, destructive cancels, external writes) remain disabled until explicitly enabled elsewhere

## Audit events

| Action | When |
|--------|------|
| `AI_BUSINESS_SETUP_STARTED` | Analyze begins |
| `AI_BUSINESS_RECOMMENDATION_GENERATED` | Recommendation stored as draft |
| `AI_BUSINESS_SETUP_REVIEWED` | Draft saved after owner edits |
| `AI_BUSINESS_SETUP_CONFIRMED` | Confirm succeeds |
| `AI_BUSINESS_SETUP_FAILED` | Analyze fails hard |
| `crm_configuration_ai_setup` | CRM modules/fields applied |

Payloads include tenant, actor, operation id (on confirm), outcome summaries — not full prompts or secrets.

## RBAC

```text
business_setup.read
business_setup.generate
business_setup.update
business_setup.confirm
```

Owners receive all catalog permissions via the existing RBAC seed model.

## UI

`/onboarding/ai-setup` — describe → analyze (real loading stages) → clarify → editable review → confirm dialog → success.

Nav: **AI setup** under admin (`business_setup.read`).

## Configuration

Reuses existing OpenAI settings (`openai_api_key`, `call_intelligence_model` when present). No second AI client. No hardcoded API keys.

## Known limitations

- Live OpenAI refinement is **NOT VERIFIED** in staging/production without provider credentials.
- Product recommendations are category suggestions only; catalog SKUs are not created on confirm (by design).
- AI configuration is stored as a recommendation blob for Phase 30 agent wiring — risky tools are not auto-enabled.

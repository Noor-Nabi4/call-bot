/** Phase 29 AI Business Setup API client. */

import { api } from "./client";
export { confidenceLabel } from "./business-setup-format";

export type ConfidenceBand = "high" | "medium" | "low";

export type ClarificationQuestion = {
  id: string;
  prompt: string;
  options: string[];
};

export type BusinessProfileRec = {
  industry: string;
  industry_confidence: ConfidenceBand;
  business_models: string[];
  business_model_confidence: ConfidenceBand;
  service_area?: string | null;
  customer_type?: string | null;
  field_service: boolean;
  appointment_based: boolean;
  membership_based: boolean;
  inventory_required: boolean;
  equipment_tracking_required: boolean;
  summary?: string | null;
};

export type ModuleRec = {
  key: string;
  recommended: boolean;
  selected: boolean;
  reason: string;
  confidence: ConfidenceBand;
};

export type CustomFieldRec = {
  name: string;
  field_key: string;
  entity: string;
  reason: string;
  selected: boolean;
};

export type ServiceRec = {
  name: string;
  description?: string | null;
  reason: string;
  selected: boolean;
  price: null;
};

export type ProductCategoryRec = {
  name: string;
  reason: string;
  selected: boolean;
};

export type AiConfigRec = {
  recommended: boolean;
  primary_purpose: string;
  tone?: string | null;
  greeting_suggestion?: string | null;
  capabilities: string[];
  risky_actions_disabled: string[];
};

export type SetupRecommendation = {
  business_profile: BusinessProfileRec;
  modules: ModuleRec[];
  custom_fields: CustomFieldRec[];
  services: ServiceRec[];
  product_categories: ProductCategoryRec[];
  ai_configuration: AiConfigRec;
  clarifications: ClarificationQuestion[];
  source: "heuristic" | "openai" | "edited";
};

export type BusinessSetupState = {
  status: string;
  description?: string | null;
  recommendation?: SetupRecommendation | null;
  operation_id?: string | null;
  confirmed_at?: string | null;
  last_confirm_result?: Record<string, unknown> | null;
  updated_at?: string | null;
};

export function getBusinessSetup() {
  return api<{ setup: BusinessSetupState }>("/api/admin/business-setup");
}

export function analyzeBusiness(
  description: string,
  clarificationAnswers: Record<string, string> = {},
) {
  return api<{ setup: BusinessSetupState }>("/api/admin/business-setup/analyze", {
    method: "POST",
    body: JSON.stringify({
      description,
      clarification_answers: clarificationAnswers,
    }),
  });
}

export function saveRecommendationDraft(recommendation: SetupRecommendation) {
  return api<{ setup: BusinessSetupState }>(
    "/api/admin/business-setup/recommendation",
    {
      method: "PUT",
      body: JSON.stringify({ recommendation }),
    },
  );
}

export function confirmBusinessSetup(params: {
  operation_id: string;
  recommendation: SetupRecommendation;
  create_services?: boolean;
  apply_crm_modules?: boolean;
}) {
  return api<{
    status: string;
    idempotent: boolean;
    result: Record<string, unknown>;
  }>("/api/admin/business-setup/confirm", {
    method: "POST",
    body: JSON.stringify({
      operation_id: params.operation_id,
      recommendation: params.recommendation,
      create_services: params.create_services ?? true,
      apply_crm_modules: params.apply_crm_modules ?? true,
    }),
  });
}

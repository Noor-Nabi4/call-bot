/** Phase 30 AI Agent Configuration API client. */

import { api } from "./client";

export type VoiceOption = {
  key: string;
  display_name: string;
  provider: string;
  languages: string[];
  available: boolean;
};

export type LanguageOption = { code: string; display_name: string };
export type ToneOption = {
  key: string;
  display_name: string;
  description: string;
};

export type CapabilityState = {
  key: string;
  display_name: string;
  description: string;
  risk_level: string;
  category: string;
  enabled: boolean;
  requested: boolean;
  available: boolean;
  missing_modules: string[];
  unavailable_reason: string | null;
  confirmation_required?: boolean;
  tool_names?: string[];
};

export type AgentConfig = {
  id: string;
  name: string;
  assistant_name?: string | null;
  voice: string;
  language: string;
  tone?: string | null;
  greeting?: string | null;
  custom_instructions?: string | null;
  business_description?: string | null;
  business_hours_summary?: string | null;
  business_hours?: Record<string, string[][]>;
  handoff_rules_text?: string | null;
  supported_languages?: string[];
  response_style?: string | null;
  status: string;
  profile_version: number;
  is_default?: boolean;
  capabilities: Record<string, boolean>;
  capability_states: CapabilityState[];
  transfer_rules: Record<string, boolean>;
  escalation_rules: Record<string, boolean>;
  after_hours_behavior: string;
  enabled_modules: string[];
  enabled_tools?: Record<string, boolean>;
};

export type GuardrailsCatalog = {
  authoritative_data: Array<{ key: string; tools: string[] }>;
  confirmation_required_tools: Array<{
    tool: string;
    operation: string;
    tool_group: string;
    mutation: boolean;
    idempotency_required: boolean;
  }>;
  note: string;
};

export type AgentConfigCatalog = {
  voices: VoiceOption[];
  languages: LanguageOption[];
  tones: ToneOption[];
  capabilities: Array<{
    key: string;
    display_name: string;
    description: string;
    risk_level: string;
    category: string;
    required_modules: string[];
    confirmation_required?: boolean;
  }>;
  guardrails?: GuardrailsCatalog;
  transfer_rules: Array<{ key: string; display_name: string }>;
  escalation_rules: Array<{ key: string; display_name: string }>;
  after_hours_behaviors: Array<{ key: string; display_name: string }>;
  escalation_priority: string[];
};

export function getAgentConfigCatalog() {
  return api<{ catalog: AgentConfigCatalog }>("/api/admin/agent-config/catalog");
}

export function getAgentConfig(profileId: string) {
  return api<{ config: AgentConfig }>(
    `/api/admin/agent-config/profiles/${profileId}`,
  );
}

export function updateAgentConfig(
  profileId: string,
  body: Record<string, unknown>,
) {
  return api<{ config: AgentConfig }>(
    `/api/admin/agent-config/profiles/${profileId}`,
    { method: "PUT", body: JSON.stringify(body) },
  );
}

export function activateAgentConfig(
  profileId: string,
  operationId?: string,
) {
  return api<{ config: AgentConfig }>(
    `/api/admin/agent-config/profiles/${profileId}/activate`,
    {
      method: "POST",
      body: JSON.stringify({ operation_id: operationId ?? null }),
    },
  );
}

export function riskLabel(level: string): string {
  if (level === "high") return "High risk";
  if (level === "medium") return "Medium risk";
  return "Low risk";
}

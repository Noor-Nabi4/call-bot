import type { AgentProfile, IndustryTemplate } from "@/types";
import { api } from "./client";

export function listIndustryTemplates() {
  return api<{ templates: IndustryTemplate[] }>("/api/admin/industry-templates");
}

export function listAgentProfiles(includeArchived = false) {
  const q = includeArchived ? "?include_archived=true" : "";
  return api<{ profiles: AgentProfile[]; business_name: string }>(
    `/api/admin/agent-profiles${q}`,
  );
}

export function getAgentProfile(id: string) {
  return api<{ profile: AgentProfile; business_name: string }>(
    `/api/admin/agent-profiles/${id}`,
  );
}

export function createAgentProfile(
  body: Partial<AgentProfile> & { name: string; agent_type?: string },
) {
  return api<{ profile: AgentProfile; business_name: string }>(
    "/api/admin/agent-profiles",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function updateAgentProfile(id: string, body: Partial<AgentProfile>) {
  return api<{ profile: AgentProfile; business_name: string }>(
    `/api/admin/agent-profiles/${id}`,
    { method: "PUT", body: JSON.stringify(body) },
  );
}

export function archiveAgentProfile(id: string) {
  return api<{ profile: AgentProfile }>(`/api/admin/agent-profiles/${id}`, {
    method: "DELETE",
  });
}

export function setDefaultAgentProfile(id: string) {
  return api<{ profile: AgentProfile }>(
    `/api/admin/agent-profiles/${id}/set-default`,
    { method: "POST" },
  );
}

export function applyAgentTemplate(
  id: string,
  industryKey: string,
  seedKnowledge = true,
) {
  return api<{ profile: AgentProfile; business_name: string }>(
    `/api/admin/agent-profiles/${id}/apply-template`,
    {
      method: "POST",
      body: JSON.stringify({
        industry_key: industryKey,
        seed_knowledge: seedKnowledge,
      }),
    },
  );
}

export function getMarketplaceCatalog() {
  return api<{
    templates: IndustryTemplate[];
    categories: string[];
    featured: IndustryTemplate[];
  }>("/api/admin/marketplace");
}

export function installMarketplaceAgent(body: {
  industry_key: string;
  name?: string;
  set_as_default?: boolean;
  seed_knowledge?: boolean;
}) {
  return api<{ profile: AgentProfile; business_name: string }>(
    "/api/admin/marketplace/install",
    { method: "POST", body: JSON.stringify(body) },
  );
}

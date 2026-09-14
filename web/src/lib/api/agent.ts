import type { AgentSettings } from "@/types";
import { api } from "./client";

export function getAgentSettings() {
  return api<{ settings: AgentSettings | null; business_name: string }>(
    "/api/admin/agent-settings",
  );
}

export function updateAgentSettings(
  body: Omit<AgentSettings, "profile_version" | "updated_at" | "tenant_id">,
) {
  return api<{ settings: AgentSettings; business_name: string }>(
    "/api/admin/agent-settings",
    {
      method: "PUT",
      body: JSON.stringify(body),
    },
  );
}

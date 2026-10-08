/** Phase 28 integrations API client. */

import { api } from "./client";
export { statusLabel } from "./integrations-format";

export type IntegrationCategory = "crm" | "calendar" | "commerce" | "accounting";

export type IntegrationStatus =
  | "DISCONNECTED"
  | "CONNECTING"
  | "CONNECTED"
  | "SYNCING"
  | "SYNCED"
  | "ERROR"
  | "REAUTH_REQUIRED"
  | "DISABLED";

export type ProviderDescriptor = {
  key: string;
  name: string;
  category: IntegrationCategory;
  description: string;
  capabilities: string[];
  oauth: boolean;
  default_sync_direction: string;
  platform_configured: boolean;
};

export type IntegrationConnection = {
  id: string;
  tenant_id: string;
  category: IntegrationCategory;
  provider: string;
  provider_name: string;
  status: IntegrationStatus;
  display_name: string | null;
  external_account_id: string | null;
  sync_direction: string;
  connected_at: string | null;
  last_sync_at: string | null;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  credentials: {
    has_access_token: boolean;
    has_refresh_token: boolean;
    token_type: string | null;
    scope: string | null;
    expires_at: string | null;
  } | null;
  capabilities: string[];
  health?: { status: string; message: string | null };
  recent_sync_runs?: SyncRun[];
};

export type SyncRun = {
  id: string;
  integration_id: string;
  status: string;
  direction: string;
  records_processed: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
};

export function listIntegrationProviders() {
  return api<{ providers: ProviderDescriptor[] }>(
    "/api/admin/integrations/providers",
  );
}

export function listIntegrations() {
  return api<{ integrations: IntegrationConnection[] }>(
    "/api/admin/integrations",
  );
}

export function getIntegration(id: string) {
  return api<{ integration: IntegrationConnection }>(
    `/api/admin/integrations/${id}`,
  );
}

export function startConnect(
  provider: string,
  redirectUri: string,
  shop?: string,
) {
  return api<{
    integration_id: string;
    authorization_url: string;
    provider: string;
  }>(`/api/admin/integrations/${provider}/connect`, {
    method: "POST",
    body: JSON.stringify({
      redirect_uri: redirectUri,
      shop: shop || null,
    }),
  });
}

export function completeOAuthCallback(
  provider: string,
  state: string,
  code: string,
) {
  return api<{ integration: IntegrationConnection }>(
    `/api/admin/integrations/${provider}/callback`,
    {
      method: "POST",
      body: JSON.stringify({ state, code }),
    },
  );
}

export function connectApiKey(
  provider: string,
  credentials: Record<string, string>,
  displayName?: string,
) {
  return api<{ integration: IntegrationConnection }>(
    `/api/admin/integrations/${provider}/api-key`,
    {
      method: "POST",
      body: JSON.stringify({
        credentials,
        display_name: displayName || null,
      }),
    },
  );
}

export function syncIntegration(id: string) {
  return api<{ sync_run: SyncRun; async_job_id: string }>(
    `/api/admin/integrations/${id}/sync`,
    { method: "POST" },
  );
}

export function disconnectIntegration(id: string) {
  return api<{ integration: IntegrationConnection }>(
    `/api/admin/integrations/${id}`,
    { method: "DELETE" },
  );
}

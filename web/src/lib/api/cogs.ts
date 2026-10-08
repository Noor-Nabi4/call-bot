/** Platform COGS types. Browser helpers refuse organization sessions. */

export type CogsPeriod =
  | "today"
  | "7d"
  | "30d"
  | "this_month"
  | "last_month"
  | "custom";

export type VariableCogs = {
  openai_usd: number;
  livekit_agent_usd: number;
  livekit_sip_usd: number;
  livekit_bvc_usd: number;
  twilio_origination_usd: number;
  twilio_termination_usd: number;
  total_usd: number;
  cogs_per_minute_usd: number | null;
};

export type CogsBucketRow = {
  key: string;
  call_count: number;
  billable_seconds: number;
  vendor_minutes: number;
  total_estimated_cogs_usd: number;
  cogs_per_minute_usd?: number | null;
  revenue_usd?: number | null;
  gross_profit_usd?: number | null;
  gross_margin_pct?: number | null;
};

export type CogsCallRow = {
  call_id: string;
  started_at: string | null;
  channel: string | null;
  transfer_kind: string | null;
  billable_seconds: number;
  vendor_minutes: number;
  total_estimated_cogs_usd: number;
  cogs_per_minute_usd?: number | null;
  openai_usd?: number;
  livekit_usd?: number;
  twilio_usd?: number;
};

export type CogsSummary = {
  period: string;
  variable_cogs: VariableCogs;
  gross_margin_pct: number | null;
  revenue_usd?: number | null;
  by_channel?: CogsBucketRow[];
  daily?: Array<{ date: string; cogs_usd: number }>;
};

export type CogsScenarios = Record<string, unknown>;

export type CogsCallsResponse = {
  calls: CogsCallRow[];
  total: number;
};

export type CogsQuery = {
  period?: CogsPeriod;
  start?: string;
  end?: string;
  channel?: string;
  transfer_kind?: string;
  call_id?: string;
  limit?: number;
  offset?: number;
};

const ORG_COGS_BLOCKED =
  "Platform COGS APIs are not available to organization sessions. Use /settings/usage.";

function rejectOrganizationCogsClient<T>(): Promise<T> {
  return Promise.reject(new Error(ORG_COGS_BLOCKED));
}

/** @deprecated Organization clients must not call platform COGS. */
export function getCogsSummary(_params: CogsQuery = {}) {
  return rejectOrganizationCogsClient<{ cogs: CogsSummary }>();
}

/** @deprecated Organization clients must not call platform COGS. */
export function getCogsScenarios() {
  return rejectOrganizationCogsClient<{ scenarios: CogsScenarios }>();
}

/** @deprecated Organization clients must not call platform COGS. */
export function listCogsCalls(_params: CogsQuery = {}) {
  return rejectOrganizationCogsClient<CogsCallsResponse>();
}

/** @deprecated Organization clients must not call platform COGS. */
export function getCogsCall(_callId: string) {
  return rejectOrganizationCogsClient<{ call: CogsCallRow }>();
}

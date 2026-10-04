import { api } from "./client";

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
};

export type CogsDailyPoint = {
  date: string;
  call_count: number;
  billable_seconds: number;
  vendor_minutes: number;
  cogs_usd: number;
  revenue_usd: number | null;
  gross_profit_usd: number | null;
  gross_margin_pct: number | null;
  note?: string;
};

export type PlanProfitabilityRow = {
  plan_key: string;
  customers: number | null;
  call_count: number;
  vendor_minutes: number;
  revenue_usd: number | null;
  cogs_usd: number;
  gross_profit_usd: number | null;
  gross_margin_pct: number | null;
  customers_unavailable?: boolean;
};

export type CogsSummary = {
  period_start: string;
  period_end: string;
  period_kind: string;
  plan_key: string | null;
  call_count: number;
  billable_seconds: number;
  vendor_minutes: number;
  customer_voice_minutes: number | null;
  included_minutes: number | null;
  overage_minutes: number | null;
  variable_cogs: VariableCogs;
  livekit_agent_included_adjustment: {
    agent_cost_before_included_usd: number;
    agent_cost_after_included_usd: number;
    included_minutes_applied: number;
  };
  fixed_monthly: {
    livekit_fixed_monthly_usd: number;
    phone_rental_monthly_usd: number;
    sms_monthly_usd: number;
    total_fixed_monthly_usd: number;
    note?: string;
  };
  gross_revenue: {
    subscription_cents: number | null;
    estimated_overage_cents: number | null;
    total_cents: number | null;
    total_usd: number | null;
    revenue_per_minute_usd?: number | null;
    note?: string;
  };
  gross_profit_usd: number | null;
  gross_margin_pct: number | null;
  by_channel: CogsBucketRow[];
  by_transfer_kind: CogsBucketRow[];
  daily_series: CogsDailyPoint[];
  plan_profitability: PlanProfitabilityRow[];
  estimated: boolean;
};

export type CogsCallRow = {
  id: string;
  call_id: string;
  tenant_id: string;
  customer_id: string | null;
  customer_name: string | null;
  started_at: string | null;
  ended_at: string | null;
  channel: string;
  transfer_kind: string;
  billable_seconds: number;
  vendor_minutes: number;
  openai_cost_usd: number;
  livekit_agent_cost_usd: number;
  livekit_sip_cost_usd: number;
  livekit_bvc_cost_usd: number;
  twilio_origination_cost_usd: number;
  twilio_termination_cost_usd: number;
  total_estimated_cogs_usd: number;
  openai_cost_source: string;
  revenue_usd: number | null;
  gross_profit_usd: number | null;
  gross_margin_pct: number | null;
  created_at: string | null;
  estimated: boolean;
  openai_usage?: Record<string, number | string | null>;
  rate_snapshot?: Record<string, unknown>;
  notes?: string[];
  caller_number?: string | null;
  called_number?: string | null;
  status?: string;
  room_name?: string;
};

export type CogsCallsResponse = {
  period_start: string;
  period_end: string;
  period_kind: string;
  total: number;
  limit: number;
  offset: number;
  calls: CogsCallRow[];
  estimated: boolean;
  note?: string;
};

export type CogsScenarios = {
  scale_minutes: Array<{
    minutes: number;
    channel: string;
    transfer_kind: string;
    openai_per_minute_usd: number;
    livekit_plan: string;
    variable: {
      openai_usd: number;
      livekit_agent_usd: number;
      livekit_sip_usd: number;
      livekit_bvc_usd: number;
      twilio_origination_usd: number;
      twilio_termination_usd: number;
      total_variable_usd: number;
    };
    variable_after_agent_included_usd: number;
    fixed_monthly: {
      livekit_fixed_monthly_usd: number;
      phone_rental_monthly_usd: number;
      sms_monthly_usd: number;
      total_fixed_monthly_usd: number;
    };
    notes: string[];
  }>;
  openai_sensitivity: {
    label: string;
    scenarios: Record<string, CogsScenarios["scale_minutes"]>;
  };
  ship_vs_scale: {
    label: string;
    ship: CogsScenarios["scale_minutes"];
    scale: CogsScenarios["scale_minutes"];
  };
  fixed_monthly: {
    livekit_fixed_monthly_usd: number;
    phone_rental_monthly_usd: number;
    sms_monthly_usd: number;
    total_fixed_monthly_usd: number;
  };
  assumptions: string[];
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

function toQuery(params: CogsQuery): string {
  const q = new URLSearchParams();
  if (params.period) q.set("period", params.period);
  if (params.start) q.set("start", params.start);
  if (params.end) q.set("end", params.end);
  if (params.channel) q.set("channel", params.channel);
  if (params.transfer_kind) q.set("transfer_kind", params.transfer_kind);
  if (params.call_id) q.set("call_id", params.call_id);
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function getCogsSummary(params: CogsQuery = {}) {
  return api<{ cogs: CogsSummary }>(`/api/admin/cogs/summary${toQuery(params)}`);
}

export function getCogsScenarios() {
  return api<{ scenarios: CogsScenarios }>("/api/admin/cogs/scenarios");
}

export function listCogsCalls(params: CogsQuery = {}) {
  return api<CogsCallsResponse>(`/api/admin/cogs/calls${toQuery(params)}`);
}

export function getCogsCall(callId: string) {
  return api<{ call: CogsCallRow }>(`/api/admin/cogs/calls/${callId}`);
}

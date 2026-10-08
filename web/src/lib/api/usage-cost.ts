/** Phase 32 usage ledger + org COGS API client. */

import { api } from "./client";
export {
  formatNullablePct,
  formatNullableUsd,
  provenanceLabel,
} from "./usage-cost-format";

export type Provenance =
  | "ACTUAL_PROVIDER"
  | "ACTUAL_INTERNAL"
  | "CONFIGURED_RATE"
  | "ALLOCATED_COST"
  | "ESTIMATED"
  | "UNAVAILABLE";

export type MoneyProvenance = {
  usd: number | null;
  micros?: number | null;
  provenance: Provenance;
  available?: boolean;
};

export type UsageCostSummary = {
  period_start: string;
  period_end: string;
  period_kind: string;
  plan_key: string | null;
  usage: {
    voice_minutes: number;
    llm_input_tokens: number;
    llm_output_tokens: number;
    ai_requests: number;
    tool_calls: number;
    sms: number;
    transcription_seconds: number;
    storage_bytes: number;
    provenance?: Record<string, Provenance | string>;
  };
  limits: {
    included_minutes: number | null;
    voice_minutes_used: number;
    overage_minutes: number;
    overage_per_minute_cents: number | null;
    estimated_overage_cents: number | null;
  };
  cost: {
    voice_usd: number | null;
    llm_usd: number | null;
    sms_usd: number | null;
    transcription_usd: number | null;
    storage_usd: number | null;
    infrastructure_usd: number | null;
    total_cogs_usd: number | null;
    cost_basis_note: string;
    provenance?: Record<string, Provenance | string>;
  };
  revenue: {
    actual_revenue_cents?: number | null;
    actual_revenue_usd?: number | null;
    actual_revenue_provenance?: Provenance | string;
    configured_subscription_revenue_cents?: number | null;
    configured_subscription_revenue_usd?: number | null;
    configured_subscription_provenance?: Provenance | string;
    estimated_overage_revenue_cents?: number | null;
    estimated_overage_revenue_usd?: number | null;
    estimated_overage_provenance?: Provenance | string;
    estimated_overage_billing_status?: string;
    subscription_cents: number | null;
    estimated_overage_cents: number | null;
    total_cents: number | null;
    combined_configured_plus_estimated_cents?: number | null;
    currency: string;
    note: string;
  };
  gross_margin: {
    verified?: boolean;
    actual_gross_margin_usd?: number | null;
    actual_gross_margin_pct?: number | null;
    calculated_gross_margin_usd?: number | null;
    calculated_gross_margin_pct?: number | null;
    revenue_usd: number | null;
    cogs_usd: number | null;
    gross_margin_usd: number | null;
    gross_margin_pct: number | null;
    note?: string;
  };
  stripe_metering?: {
    wired: boolean;
    status: string;
    note: string;
  };
  daily_series: Array<{
    date: string;
    usage: Record<string, number>;
    cost_usd: number | null;
  }>;
};

export type LimitStatus = {
  usage_type: string;
  used: number;
  limit: number | null;
  percent: number | null;
  state: string;
  overage_minutes: number | null;
  blocking: boolean;
  note: string;
};

export function getUsageCostSummary() {
  return api<{ usage_cost: UsageCostSummary; limit_status: LimitStatus }>(
    "/api/admin/usage-cost/summary",
  );
}

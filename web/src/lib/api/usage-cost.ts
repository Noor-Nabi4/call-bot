/** Customer-facing organization usage API (no platform COGS/margin). */

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

/** Organization-boundary usage response — never includes provider COGS or margin. */
export type UsageCostSummary = {
  period_start: string;
  period_end: string;
  period_kind: string;
  plan_key: string | null;
  boundary?: "organization" | "platform";
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
  billing: {
    currency: string;
    estimated_overage_cents: number | null;
    estimated_overage_usd: number | null;
    estimated_overage_status?: string;
    plan_subscription_status?: string | null;
    note: string;
  };
  stripe_metering?: {
    wired: boolean;
    status: string;
    note: string;
  };
  daily_series: Array<{
    date: string;
    usage: Record<string, number>;
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

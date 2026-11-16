/** Phase 27 analytics API client (`GET /api/admin/analytics`). */

import { api } from "./client";
export { formatDurationSeconds } from "./analytics-format";

export type AnalyticsPreset =
  | "today"
  | "yesterday"
  | "last_7_days"
  | "last_30_days"
  | "this_month"
  | "last_month"
  | "custom";

export type AnalyticsRange = {
  from: string;
  to: string;
  timezone: string;
  preset: string;
  local_from: string;
  local_to: string;
  inclusive_end_date: boolean;
  bound_style: string;
};

export type CallsAnalytics = {
  total: number;
  ended: number;
  answer_rate: number | null;
  answer_rate_unavailable?: string | null;
  missed: number | null;
  missed_unavailable?: string | null;
  average_duration_seconds: number | null;
  transfer_rate: number | null;
  transfers: number;
  ai_resolution_rate: number | null;
  ai_resolved: number;
  calls_by_day: { date: string; calls: number }[];
  disconnect_reasons: Record<string, number>;
  reviewed_dispositions: number;
};

export type SalesAnalytics = {
  leads: number;
  qualified_leads: number;
  qualification_rate: number | null;
  bookings: number;
  conversion_rate: number | null;
  converted_leads: number;
  revenue: number;
  revenue_per_lead: number | null;
  revenue_per_lead_unavailable?: string | null;
  revenue_per_call: number | null;
  revenue_per_call_unavailable?: string | null;
  product_sales: number;
  leads_by_status: Record<string, number>;
  leads_by_source: Record<string, number>;
  leads_by_day: { date: string; leads: number }[];
  bookings_by_day: { date: string; bookings: number }[];
  top_products: {
    product_id: string | null;
    name: string;
    units: number;
    revenue: number;
  }[];
  funnel: {
    leads: number;
    qualified: number;
    booked_or_won: number;
    bookings: number;
  };
};

export type OperationsAnalytics = {
  jobs_completed: number;
  jobs_created: number;
  cancellation_rate: number | null;
  cancelled_jobs: number;
  no_show_rate: number | null;
  no_show_count: number;
  technician_utilization: number | null;
  technician_utilization_unavailable?: string | null;
  average_job_duration_seconds: number | null;
  average_job_duration_unavailable?: string | null;
  avg_lead_response_seconds: number | null;
  avg_lead_response_unavailable?: string | null;
  jobs_completed_by_day: { date: string; completed: number }[];
  jobs_by_status: Record<string, number>;
  technicians: {
    technician_id: string;
    display_name: string;
    assigned: number;
    completed: number;
    utilization: number | null;
    avg_duration_seconds: number | null;
  }[];
};

export type AnalyticsOverview = {
  range: AnalyticsRange;
  definitions: Record<string, unknown>[];
  calls: CallsAnalytics;
  sales: SalesAnalytics;
  operations: OperationsAnalytics;
};

export type AnalyticsQuery = {
  preset?: AnalyticsPreset;
  from_date?: string;
  to_date?: string;
};

function qs(params: AnalyticsQuery): string {
  const sp = new URLSearchParams();
  if (params.preset) sp.set("preset", params.preset);
  if (params.from_date) sp.set("from_date", params.from_date);
  if (params.to_date) sp.set("to_date", params.to_date);
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function getAnalyticsOverview(
  params: AnalyticsQuery = {},
): Promise<AnalyticsOverview> {
  return api(`/api/admin/analytics${qs(params)}`);
}

export function getCallsAnalytics(
  params: AnalyticsQuery = {},
): Promise<{ range: AnalyticsRange; calls: CallsAnalytics }> {
  return api(`/api/admin/analytics/calls${qs(params)}`);
}

export function getSalesAnalytics(
  params: AnalyticsQuery = {},
): Promise<{ range: AnalyticsRange; sales: SalesAnalytics }> {
  return api(`/api/admin/analytics/sales${qs(params)}`);
}

export function getOperationsAnalytics(
  params: AnalyticsQuery = {},
): Promise<{ range: AnalyticsRange; operations: OperationsAnalytics }> {
  return api(`/api/admin/analytics/operations${qs(params)}`);
}


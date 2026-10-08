/** Admin metrics summary (`GET /api/admin/metrics`). */

import { api } from "./client";
export { formatMoney, formatPercent } from "./metrics-format";

export type DayPoint = { date: string; calls: number };

export type RevenueDayPoint = { date: string; revenue: number };

export type AdminMetrics = {
  window_days: number;
  calls: number;
  calls_ended: number;
  calls_active: number;
  voice_minutes: number;
  avg_call_duration_seconds: number;
  avg_quality_score?: number | null;
  quality_reviews?: number;
  handoffs_requested: number;
  handoff_rate: number;
  /** Fraction of ended calls without handoff; null when no ended calls. */
  ai_resolution_rate?: number | null;
  appointment_booked_calls: number;
  appointments: number;
  jobs: number;
  jobs_completed: number;
  customers: number;
  leads: number;
  leads_by_status: Record<string, number>;
  revenue: number;
  revenue_by_day: RevenueDayPoint[];
  outstanding_invoices: number;
  outstanding_balance: number;
  jobs_by_status: Record<string, number>;
  disconnect_reasons: Record<string, number>;
  calls_by_day: DayPoint[];
};

export async function getAdminMetrics(days = 30): Promise<AdminMetrics> {
  const res = await api<{ metrics: AdminMetrics }>(
    `/api/admin/metrics?days=${Math.max(1, Math.min(days, 365))}`,
  );
  return res.metrics;
}

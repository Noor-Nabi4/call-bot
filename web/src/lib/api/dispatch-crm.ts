/** Typed helpers for Dispatch CRM APIs (Phase 12). */

import { api } from "./client";

export type DispatchTechnician = {
  id: string;
  display_name: string;
  phone?: string | null;
  is_active: boolean;
  status: string;
  status_since?: string | null;
};

export type DispatchJobCard = {
  id: string;
  job_number: string;
  reference_code?: string | null;
  status: string;
  priority: string;
  service_type: string;
  scheduled_starts_at?: string | null;
  scheduled_ends_at?: string | null;
  eta?: string | null;
  eta_source?: string | null;
  assigned_technician_id?: string | null;
  assigned_at?: string | null;
  customer?: {
    id: string;
    name?: string | null;
    display_name?: string | null;
  } | null;
  location?: {
    id: string;
    address_line_1?: string | null;
    city?: string | null;
    postal_code?: string | null;
  } | null;
  conflict?: boolean;
};

export type DispatchBoard = {
  date: string;
  timezone: string;
  window_start: string;
  window_end: string;
  technicians: DispatchTechnician[];
  unassigned_jobs: DispatchJobCard[];
  assigned_jobs: DispatchJobCard[];
  generated_at: string;
};

export type DispatchEvent = {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at?: string | null;
};

export async function getDispatchBoard(params: {
  date?: string;
  technician_id?: string;
  status?: string;
  priority?: string;
  assigned?: string;
  q?: string;
  limit?: number;
}): Promise<DispatchBoard> {
  const sp = new URLSearchParams();
  if (params.date) sp.set("date", params.date);
  if (params.technician_id) sp.set("technician_id", params.technician_id);
  if (params.status) sp.set("status", params.status);
  if (params.priority) sp.set("priority", params.priority);
  if (params.assigned) sp.set("assigned", params.assigned);
  if (params.q) sp.set("q", params.q);
  if (params.limit) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return api(`/api/admin/crm/dispatch/board${qs ? `?${qs}` : ""}`);
}

export async function assignDispatchJob(
  jobId: string,
  body: {
    technician_id: string | null;
    reason?: string;
    eta?: string;
    eta_source?: string;
  },
  idempotencyKey?: string,
): Promise<{ job: Record<string, unknown> }> {
  const headers: Record<string, string> = {};
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return api(`/api/admin/crm/dispatch/jobs/${jobId}/assign`, {
    method: "POST",
    body: JSON.stringify(body),
    headers,
  });
}

export async function getDispatchEvents(params?: {
  after_id?: string;
  limit?: number;
}): Promise<{ events: DispatchEvent[] }> {
  const sp = new URLSearchParams();
  if (params?.after_id) sp.set("after_id", params.after_id);
  if (params?.limit) sp.set("limit", String(params.limit));
  const qs = sp.toString();
  return api(`/api/admin/crm/dispatch/events${qs ? `?${qs}` : ""}`);
}

export async function setTechnicianOperationalStatus(
  technicianId: string,
  body: { to_status: string; reason?: string },
): Promise<{ status: Record<string, unknown> }> {
  return api(`/api/admin/crm/dispatch/technicians/${technicianId}/status`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getTechnicianOpsDetail(
  technicianId: string,
): Promise<Record<string, unknown>> {
  return api(`/api/admin/crm/dispatch/technicians/${technicianId}`);
}

export const TECH_OPS_STATUSES = [
  "AVAILABLE",
  "BUSY",
  "EN_ROUTE",
  "ARRIVED",
  "ON_BREAK",
  "OFFLINE",
] as const;

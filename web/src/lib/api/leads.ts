/** Typed helpers for Lead CRM admin APIs (Phase 8). */

import { api } from "./client";

export type LeadStatus =
  | "NEW"
  | "QUALIFIED"
  | "CONTACTED"
  | "BOOKED"
  | "WON"
  | "LOST";

export type LeadPriority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";

export type LeadSource =
  | "PHONE"
  | "WEBSITE"
  | "REFERRAL"
  | "SOCIAL"
  | "EMAIL"
  | "AD"
  | "WALK_IN"
  | "AI_AGENT"
  | "OTHER";

export const LEAD_STATUSES: LeadStatus[] = [
  "NEW",
  "QUALIFIED",
  "CONTACTED",
  "BOOKED",
  "WON",
  "LOST",
];

export const LEAD_PRIORITIES: LeadPriority[] = [
  "LOW",
  "MEDIUM",
  "HIGH",
  "URGENT",
];

export const LEAD_SOURCES: LeadSource[] = [
  "PHONE",
  "WEBSITE",
  "REFERRAL",
  "SOCIAL",
  "EMAIL",
  "AD",
  "WALK_IN",
  "AI_AGENT",
  "OTHER",
];

export type LeadRef = {
  id: string;
  name?: string | null;
  display_name?: string | null;
  email?: string | null;
  code?: string | null;
  sku?: string | null;
  status?: string | null;
};

export type LeadConversion = {
  id: string;
  lead_id: string;
  customer_id: string;
  created_customer: boolean;
  converted_by?: string | null;
  created_at?: string | null;
};

export type LeadRow = {
  id: string;
  title: string;
  description?: string | null;
  source: string;
  priority: string;
  status: string;
  customer_id?: string | null;
  customer?: LeadRef | null;
  service_id?: string | null;
  service?: LeadRef | null;
  product_id?: string | null;
  product?: LeadRef | null;
  owner_user_id?: string | null;
  owner?: LeadRef | null;
  prospect_name?: string | null;
  prospect_phone?: string | null;
  prospect_email?: string | null;
  reference_code?: string;
  notes?: string | null;
  archived_at?: string | null;
  converted_at?: string | null;
  converted_customer_id?: string | null;
  conversion?: LeadConversion | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type LeadActivity = {
  id: string;
  activity_type: string;
  actor?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
};

export type LeadNote = {
  id: string;
  body: string;
  created_by?: string | null;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type PipelineCounts = {
  counts: Record<string, number>;
  total: number;
  statuses: string[];
};

type ListParams = {
  q?: string;
  status?: string;
  priority?: string;
  source?: string;
  owner_user_id?: string;
  customer_id?: string;
  service_id?: string;
  product_id?: string;
  include_archived?: boolean;
  limit?: number;
  cursor?: string;
};

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === "" || v === false) continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function listLeads(params: ListParams = {}) {
  return api<{
    leads: LeadRow[];
    next_cursor: string | null;
    limit: number;
  }>(`/api/admin/crm/leads${qs(params)}`);
}

export async function getPipelineCounts(params: {
  owner_user_id?: string;
  source?: string;
  priority?: string;
  include_archived?: boolean;
} = {}) {
  return api<PipelineCounts>(
    `/api/admin/crm/leads/pipeline/counts${qs(params)}`,
  );
}

export async function getLead(id: string) {
  const res = await api<{ lead: LeadRow }>(`/api/admin/crm/leads/${id}`);
  return res.lead;
}

export async function createLead(body: {
  title: string;
  description?: string;
  source?: string;
  priority?: string;
  customer_id?: string;
  service_id?: string;
  product_id?: string;
  owner_user_id?: string;
  prospect_name?: string;
  prospect_phone?: string;
  prospect_email?: string;
  notes?: string;
}) {
  const res = await api<{ lead: LeadRow }>("/api/admin/crm/leads", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return res.lead;
}

export async function updateLead(
  id: string,
  body: Record<string, unknown>,
) {
  const res = await api<{ lead: LeadRow }>(`/api/admin/crm/leads/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return res.lead;
}

export async function archiveLead(id: string) {
  const res = await api<{ lead: LeadRow }>(`/api/admin/crm/leads/${id}`, {
    method: "DELETE",
  });
  return res.lead;
}

export async function restoreLead(id: string) {
  const res = await api<{ lead: LeadRow }>(
    `/api/admin/crm/leads/${id}/restore`,
    { method: "POST" },
  );
  return res.lead;
}

export async function transitionLead(
  id: string,
  to_status: string,
  reason?: string,
) {
  const res = await api<{ lead: LeadRow }>(
    `/api/admin/crm/leads/${id}/transition`,
    {
      method: "POST",
      body: JSON.stringify({ to_status, reason }),
    },
  );
  return res.lead;
}

export async function convertLead(
  id: string,
  body: {
    customer_id?: string;
    create_customer?: Record<string, unknown>;
  },
) {
  return api<{
    lead: LeadRow;
    conversion: LeadConversion;
    already_converted: boolean;
  }>(`/api/admin/crm/leads/${id}/convert`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listLeadActivities(
  id: string,
  params: { limit?: number; cursor?: string } = {},
) {
  return api<{
    activities: LeadActivity[];
    next_cursor: string | null;
  }>(`/api/admin/crm/leads/${id}/activities${qs(params)}`);
}

export async function listLeadNotes(
  id: string,
  params: { limit?: number; cursor?: string; include_archived?: boolean } = {},
) {
  return api<{
    notes: LeadNote[];
    next_cursor: string | null;
  }>(`/api/admin/crm/leads/${id}/notes${qs(params)}`);
}

export async function createLeadNote(id: string, body: string) {
  const res = await api<{ note: LeadNote }>(
    `/api/admin/crm/leads/${id}/notes`,
    { method: "POST", body: JSON.stringify({ body }) },
  );
  return res.note;
}

export async function archiveLeadNote(leadId: string, noteId: string) {
  const res = await api<{ note: LeadNote }>(
    `/api/admin/crm/leads/${leadId}/notes/${noteId}`,
    { method: "DELETE" },
  );
  return res.note;
}

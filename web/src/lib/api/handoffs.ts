import { api } from "./client";

export type HandoffRow = {
  id: string;
  channel: string;
  status: string;
  reason: string;
  priority: string;
  customer_id: string | null;
  call_id: string | null;
  department: string | null;
  intent: string | null;
  summary: string | null;
  requested_at: string | null;
  connected_at: string | null;
  completed_at: string | null;
  context_snapshot?: Record<string, unknown>;
  assignment?: {
    id: string;
    assignment_type: string;
    status: string;
  };
  history?: Array<{
    id: string;
    event_type: string;
    created_at: string | null;
    payload: Record<string, unknown>;
  }>;
};

export function listHandoffs(params: {
  status?: string;
  priority?: string;
  channel?: string;
  limit?: number;
} = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.priority) qs.set("priority", params.priority);
  if (params.channel) qs.set("channel", params.channel);
  if (params.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return api<{ items: HandoffRow[]; limit: number; offset: number }>(
    `/api/admin/crm/handoffs${q ? `?${q}` : ""}`,
  );
}

export function getHandoff(id: string) {
  return api<{ handoff: HandoffRow }>(`/api/admin/crm/handoffs/${id}`);
}

export function acceptHandoff(id: string) {
  return api<{ handoff: HandoffRow }>(`/api/admin/crm/handoffs/${id}/accept`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function rejectHandoff(id: string) {
  return api<{ handoff: HandoffRow }>(`/api/admin/crm/handoffs/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function completeHandoff(id: string) {
  return api<{ handoff: HandoffRow }>(
    `/api/admin/crm/handoffs/${id}/complete`,
    { method: "POST", body: JSON.stringify({}) },
  );
}

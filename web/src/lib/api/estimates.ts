/** Typed helpers for Estimate CRM admin APIs (Phase 13). */

import { api } from "./client";

export const ESTIMATE_STATUSES = [
  "DRAFT",
  "SENT",
  "VIEWED",
  "APPROVED",
  "REJECTED",
  "EXPIRED",
  "CANCELLED",
  "CONVERTED",
] as const;

export type EstimateStatus = (typeof ESTIMATE_STATUSES)[number];

export type EstimateItemRow = {
  id: string;
  item_type: string;
  service_id?: string | null;
  product_id?: string | null;
  variant_id?: string | null;
  name_snapshot: string;
  description_snapshot?: string | null;
  sku_snapshot?: string | null;
  quantity: string;
  unit_price: string;
  discount_total: string;
  tax_total: string;
  line_subtotal: string;
  line_total: string;
  sort_order: number;
};

export type EstimateHistoryRow = {
  id: string;
  from_status?: string | null;
  to_status: string;
  changed_by?: string | null;
  reason?: string | null;
  created_at?: string | null;
};

export type EstimateConversionRow = {
  id: string;
  target_type: string;
  target_id: string;
  target_number?: string | null;
  created_at?: string | null;
};

export type EstimateRow = {
  id: string;
  estimate_number: string;
  customer_id: string;
  customer?: { id: string; name?: string | null; display_name?: string | null } | null;
  location_id?: string | null;
  title: string;
  description?: string | null;
  status: string;
  currency: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  estimate_discount: string;
  valid_until?: string | null;
  notes?: string | null;
  terms?: string | null;
  approved_at?: string | null;
  approved_by?: string | null;
  rejected_at?: string | null;
  rejected_by?: string | null;
  rejection_reason?: string | null;
  converted_at?: string | null;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  items?: EstimateItemRow[];
  status_history?: EstimateHistoryRow[];
  conversions?: EstimateConversionRow[];
};

export type EstimateLineInput = {
  item_type: "SERVICE" | "PRODUCT" | "CUSTOM";
  service_id?: string | null;
  product_id?: string | null;
  variant_id?: string | null;
  pricebook_id?: string | null;
  name?: string | null;
  description?: string | null;
  quantity: string | number;
  unit_price?: string | null;
  discount_total?: string | null;
  tax_total?: string | null;
  sort_order?: number | null;
};

export function listEstimates(params?: {
  q?: string;
  status?: string;
  customer_id?: string;
  limit?: number;
  cursor?: string;
}) {
  const q = new URLSearchParams();
  if (params?.q) q.set("q", params.q);
  if (params?.status) q.set("status", params.status);
  if (params?.customer_id) q.set("customer_id", params.customer_id);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.cursor) q.set("cursor", params.cursor);
  const qs = q.toString();
  return api<{
    estimates: EstimateRow[];
    next_cursor?: string | null;
    limit: number;
  }>(`/api/admin/crm/estimates${qs ? `?${qs}` : ""}`);
}

export function getEstimate(id: string) {
  return api<{ estimate: EstimateRow }>(`/api/admin/crm/estimates/${id}`);
}

export function createEstimate(body: {
  customer_id: string;
  items: EstimateLineInput[];
  title?: string;
  description?: string;
  location_id?: string;
  currency?: string;
  estimate_discount?: string;
  valid_until?: string;
  notes?: string;
  terms?: string;
  pricebook_id?: string;
}) {
  return api<{ estimate: EstimateRow }>("/api/admin/crm/estimates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateEstimate(
  id: string,
  body: Record<string, unknown>,
) {
  return api<{ estimate: EstimateRow }>(`/api/admin/crm/estimates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function sendEstimate(id: string) {
  return api<{ estimate: EstimateRow }>(`/api/admin/crm/estimates/${id}/send`, {
    method: "POST",
  });
}

export function approveEstimate(id: string) {
  return api<{ estimate: EstimateRow }>(
    `/api/admin/crm/estimates/${id}/approve`,
    { method: "POST" },
  );
}

export function rejectEstimate(id: string, reason?: string) {
  return api<{ estimate: EstimateRow }>(
    `/api/admin/crm/estimates/${id}/reject`,
    { method: "POST", body: JSON.stringify({ reason }) },
  );
}

export function cancelEstimate(id: string, reason?: string) {
  return api<{ estimate: EstimateRow }>(
    `/api/admin/crm/estimates/${id}/cancel`,
    { method: "POST", body: JSON.stringify({ reason }) },
  );
}

export function convertEstimate(
  id: string,
  target_type: "JOB" | "ORDER",
  idempotencyKey?: string,
) {
  const headers: Record<string, string> = {};
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return api<{
    estimate: EstimateRow;
    conversion: EstimateConversionRow;
    already_converted: boolean;
  }>(`/api/admin/crm/estimates/${id}/convert`, {
    method: "POST",
    body: JSON.stringify({ target_type }),
    headers,
  });
}

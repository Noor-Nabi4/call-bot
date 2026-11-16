/** Typed helpers for Invoice CRM admin APIs (Phase 18). */

import { api } from "./client";

export const INVOICE_STATUSES = [
  "DRAFT",
  "SENT",
  "PARTIALLY_PAID",
  "PAID",
  "OVERDUE",
  "VOID",
] as const;

export type InvoiceRow = {
  id: string;
  invoice_number: string;
  customer_id: string;
  customer?: { id: string; name?: string | null; email?: string | null } | null;
  job_id?: string | null;
  order_id?: string | null;
  estimate_id?: string | null;
  status: string;
  currency: string;
  issue_date?: string | null;
  due_date?: string | null;
  subtotal: string;
  discount_amount: string;
  invoice_discount: string;
  tax_amount: string;
  total_amount: string;
  amount_paid: string;
  balance_due: string;
  notes?: string | null;
  terms?: string | null;
  items?: InvoiceItemRow[];
  status_history?: InvoiceHistoryRow[];
  payments?: InvoicePaymentRow[];
};

export type InvoiceItemRow = {
  id: string;
  item_type: string;
  description: string;
  quantity: string;
  unit_price: string;
  discount_amount: string;
  tax_amount: string;
  line_subtotal: string;
  line_total: string;
};

export type InvoiceHistoryRow = {
  id: string;
  from_status?: string | null;
  to_status: string;
  reason?: string | null;
  created_at?: string | null;
};

export type InvoicePaymentRow = {
  id: string;
  amount: string;
  created_at?: string | null;
};

export function listInvoices(params?: {
  q?: string;
  status?: string;
  overdue_only?: boolean;
  limit?: number;
  cursor?: string;
}) {
  const q = new URLSearchParams();
  if (params?.q) q.set("q", params.q);
  if (params?.status) q.set("status", params.status);
  if (params?.overdue_only) q.set("overdue_only", "true");
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.cursor) q.set("cursor", params.cursor);
  const qs = q.toString();
  return api<{ invoices: InvoiceRow[]; next_cursor?: string | null }>(
    `/api/admin/crm/invoices${qs ? `?${qs}` : ""}`,
  );
}

export function getInvoice(id: string) {
  return api<{ invoice: InvoiceRow }>(`/api/admin/crm/invoices/${id}`);
}

export function createInvoice(body: {
  customer_id: string;
  items: Record<string, unknown>[];
  job_id?: string;
  order_id?: string;
  estimate_id?: string;
  invoice_discount?: string;
  due_date?: string;
  notes?: string;
  terms?: string;
}) {
  return api<{ invoice: InvoiceRow }>("/api/admin/crm/invoices", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function sendInvoice(id: string) {
  return api<{ invoice: InvoiceRow }>(`/api/admin/crm/invoices/${id}/send`, {
    method: "POST",
  });
}

export function voidInvoice(id: string, reason?: string) {
  return api<{ invoice: InvoiceRow }>(`/api/admin/crm/invoices/${id}/void`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

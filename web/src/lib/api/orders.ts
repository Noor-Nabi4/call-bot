/** Typed helpers for Order CRM admin APIs (Phase 9). */

import { api } from "./client";
export type { OrderStatus } from "./order-constants";
export {
  ORDER_CANCELLABLE,
  ORDER_FORWARD_TRANSITIONS,
  ORDER_STATUSES,
} from "./order-constants";

export type OrderCustomerRef = {
  id: string;
  display_name?: string | null;
  name?: string | null;
  status?: string | null;
};

export type OrderItemRow = {
  id: string;
  product_id: string;
  variant_id?: string | null;
  sku_snapshot: string;
  product_name_snapshot: string;
  variant_name_snapshot?: string | null;
  unit_price: string;
  quantity: number;
  discount_total: string;
  tax_total: string;
  line_subtotal: string;
  line_total: string;
  sort_order: number;
};

export type OrderStatusHistoryRow = {
  id: string;
  from_status?: string | null;
  to_status: string;
  changed_by?: string | null;
  reason?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
};

export type OrderRow = {
  id: string;
  order_number: string;
  customer_id: string;
  customer?: OrderCustomerRef | null;
  status: string;
  currency: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  shipping_total: string;
  total: string;
  notes?: string | null;
  shipping_address_snapshot?: Record<string, unknown> | null;
  billing_address_snapshot?: Record<string, unknown> | null;
  fulfillment_location_id?: string | null;
  inventory_reserved?: boolean;
  inventory_consumed?: boolean;
  archived_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  items?: OrderItemRow[];
  status_history?: OrderStatusHistoryRow[];
};

export type OrderListResponse = {
  orders: OrderRow[];
  next_cursor?: string | null;
  limit: number;
};

export type OrderLineInput = {
  product_id: string;
  variant_id?: string | null;
  quantity: number;
  unit_price?: string | null;
  discount_total?: string | null;
  tax_total?: string | null;
};

export type OrderCreateInput = {
  customer_id: string;
  items: OrderLineInput[];
  currency?: string;
  notes?: string;
  shipping_total?: string;
  order_discount?: string;
  fulfillment_location_id?: string;
  idempotency_key?: string;
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

export async function listOrders(params: {
  q?: string;
  status?: string;
  customer_id?: string;
  product_id?: string;
  sku?: string;
  include_archived?: boolean;
  limit?: number;
  cursor?: string;
} = {}): Promise<OrderListResponse> {
  return api<OrderListResponse>(`/api/admin/crm/orders${qs(params)}`);
}

export async function getOrder(id: string): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(`/api/admin/crm/orders/${id}`);
  return res.order;
}

export async function createOrder(
  body: OrderCreateInput,
  opts?: { idempotencyKey?: string }
): Promise<OrderRow> {
  const headers: Record<string, string> = {};
  if (opts?.idempotencyKey) {
    headers["Idempotency-Key"] = opts.idempotencyKey;
  }
  const res = await api<{ order: OrderRow }>("/api/admin/crm/orders", {
    method: "POST",
    body: JSON.stringify(body),
    headers,
  });
  return res.order;
}

export async function updateOrder(
  id: string,
  body: Record<string, unknown>
): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(`/api/admin/crm/orders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return res.order;
}

export async function archiveOrder(id: string): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(`/api/admin/crm/orders/${id}`, {
    method: "DELETE",
  });
  return res.order;
}

export async function restoreOrder(id: string): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(
    `/api/admin/crm/orders/${id}/restore`,
    { method: "POST" }
  );
  return res.order;
}

export async function transitionOrder(
  id: string,
  body: { to_status: string; reason?: string }
): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(
    `/api/admin/crm/orders/${id}/transition`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
  return res.order;
}

export async function cancelOrder(
  id: string,
  body?: { reason?: string }
): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(
    `/api/admin/crm/orders/${id}/cancel`,
    {
      method: "POST",
      body: JSON.stringify(body || {}),
    }
  );
  return res.order;
}

export async function refundOrder(
  id: string,
  body?: { reason?: string }
): Promise<OrderRow> {
  const res = await api<{ order: OrderRow }>(
    `/api/admin/crm/orders/${id}/refund`,
    {
      method: "POST",
      body: JSON.stringify(body || {}),
    }
  );
  return res.order;
}

export async function getOrderHistory(
  id: string
): Promise<{ history: OrderStatusHistoryRow[] }> {
  return api<{ history: OrderStatusHistoryRow[] }>(
    `/api/admin/crm/orders/${id}/history`
  );
}

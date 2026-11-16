import { api } from "./client";

export type InventoryBalanceRow = {
  id: string;
  inventory_item_id: string;
  location_id: string;
  location_name: string;
  location_code: string;
  product_id: string;
  product_name: string;
  variant_id: string;
  variant_name?: string | null;
  sku: string;
  stock_quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  minimum_stock: number;
  status: "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
  updated_at: string;
};

export type InventoryLocation = {
  id: string;
  name: string;
  code: string;
  description?: string | null;
  location_type: string;
  status: string;
  is_default: boolean;
  archived_at?: string | null;
};

export type InventoryTransaction = {
  id: string;
  transaction_type: string;
  quantity: number;
  stock_before: number;
  stock_after: number;
  reserved_before: number;
  reserved_after: number;
  reference_type?: string | null;
  reference_id?: string | null;
  reason?: string | null;
  created_by?: string | null;
  created_at: string;
};

export type InventoryDetail = {
  id: string;
  product_name: string;
  variant_name?: string | null;
  sku: string;
  balances: InventoryBalanceRow[];
};

const BASE = "/api/admin/crm/inventory";

export async function listInventory(params?: {
  q?: string;
  location_id?: string;
  status?: string;
  low_stock?: boolean;
  out_of_stock?: boolean;
  limit?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.location_id) qs.set("location_id", params.location_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.low_stock) qs.set("low_stock", "true");
  if (params?.out_of_stock) qs.set("out_of_stock", "true");
  if (params?.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs}` : "";
  return api<{ inventory: InventoryBalanceRow[]; next_cursor?: string | null }>(
    `${BASE}${suffix}`,
  );
}

export async function getInventoryItem(id: string) {
  return api<InventoryDetail>(`${BASE}/${id}`);
}

export async function listInventoryTransactions(
  id: string,
  params?: { location_id?: string; limit?: number },
) {
  const qs = new URLSearchParams();
  if (params?.location_id) qs.set("location_id", params.location_id);
  if (params?.limit) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs}` : "";
  return api<{ transactions: InventoryTransaction[] }>(
    `${BASE}/${id}/transactions${suffix}`,
  );
}

export async function listInventoryLocations() {
  return api<{ locations: InventoryLocation[] }>(`${BASE}/locations`);
}

export async function getInventoryDashboard() {
  return api<{
    total_inventory_items: number;
    low_stock_balances: number;
    out_of_stock_balances: number;
    recent_transactions: InventoryTransaction[];
  }>(`${BASE}/dashboard`);
}

export async function inventoryMutation(
  itemId: string,
  action:
    | "purchase"
    | "sale"
    | "adjust"
    | "return"
    | "reserve"
    | "release",
  body: {
    location_id: string;
    quantity: number;
    reason?: string;
    reference_type?: string;
    reference_id?: string;
  },
  idempotencyKey?: string,
) {
  const headers: Record<string, string> = {};
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  return api<{ transaction: InventoryTransaction; idempotent: boolean }>(
    `${BASE}/${itemId}/${action}`,
    {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    },
  );
}

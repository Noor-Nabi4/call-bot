/** Typed helpers for Services & Pricebook admin APIs. */

import { api } from "./client";

export type CatalogStatus = "ACTIVE" | "INACTIVE";
export type PricingType = "FIXED" | "STARTING_AT" | "HOURLY" | "CUSTOM_QUOTE";

export type ServiceCategory = {
  id: string;
  name: string;
  slug?: string | null;
  description?: string | null;
  parent_id?: string | null;
  status: CatalogStatus | string;
  sort_order?: number;
  service_count?: number;
  archived_at?: string | null;
  children?: ServiceCategory[];
};

export type ServiceRow = {
  id: string;
  name: string;
  code?: string | null;
  description?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  duration_minutes?: number | null;
  base_price?: string | null;
  cost?: string | null;
  tax_rate?: string | null;
  pricing_type: PricingType | string;
  status: CatalogStatus | string;
  archived_at?: string | null;
  updated_at?: string | null;
};

export type Pricebook = {
  id: string;
  name: string;
  description?: string | null;
  status: CatalogStatus | string;
  is_default: boolean;
  effective_from?: string | null;
  effective_until?: string | null;
  archived_at?: string | null;
  items?: PricebookItem[];
  overrides?: PricebookOverride[];
};

export type PricebookComponent = {
  id?: string;
  component_type: "LABOR" | "MATERIAL" | string;
  name?: string | null;
  product_variant_id?: string | null;
  variant_sku?: string | null;
  variant_name?: string | null;
  quantity?: string | null;
  unit_price?: string | null;
  line_total?: string | null;
  sort_order?: number;
};

export type PricebookItem = {
  id: string;
  pricebook_id: string;
  service_id: string;
  service_name?: string | null;
  service_code?: string | null;
  pricing_type: PricingType | string;
  price?: string | null;
  starting_price?: string | null;
  hourly_rate?: string | null;
  effective_from?: string | null;
  effective_until?: string | null;
  status: CatalogStatus | string;
  components?: PricebookComponent[];
  archived_at?: string | null;
};

export type PricebookOverride = {
  id: string;
  pricebook_id: string;
  service_id: string;
  override_price?: string | null;
  pricing_type?: string | null;
  effective_from?: string | null;
  effective_until?: string | null;
  status: CatalogStatus | string;
};

export type ResolvedPrice = {
  service_id: string;
  service_name: string;
  price?: string | null;
  pricing_type: string;
  source: string;
  pricebook_id?: string | null;
  pricebook_name?: string | null;
  duration_minutes?: number | null;
  effective_from?: string | null;
  effective_until?: string | null;
  resolved_at: string;
};

const SVC = "/api/admin/crm/services";
const CAT = "/api/admin/crm/service-categories";
const PB = "/api/admin/crm/pricebooks";

export async function listServices(params?: {
  q?: string;
  status?: string;
  category_id?: string;
  include_archived?: boolean;
  limit?: number;
  cursor?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.status) qs.set("status", params.status);
  if (params?.category_id) qs.set("category_id", params.category_id);
  if (params?.include_archived) qs.set("include_archived", "true");
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.cursor) qs.set("cursor", params.cursor);
  const suffix = qs.toString() ? `?${qs}` : "";
  return api<{ services: ServiceRow[]; next_cursor?: string | null }>(
    `${SVC}${suffix}`,
  );
}

export async function getService(id: string) {
  return api<ServiceRow>(`${SVC}/${id}`);
}

export async function createService(body: Record<string, unknown>) {
  return api<ServiceRow>(SVC, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateService(id: string, body: Record<string, unknown>) {
  return api<ServiceRow>(`${SVC}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function archiveService(id: string) {
  return api<ServiceRow>(`${SVC}/${id}`, { method: "DELETE" });
}

export async function restoreService(id: string) {
  return api<ServiceRow>(`${SVC}/${id}/restore`, { method: "POST" });
}

export async function getServicePricing(
  id: string,
  params?: { pricebook_id?: string },
) {
  const qs = new URLSearchParams();
  if (params?.pricebook_id) qs.set("pricebook_id", params.pricebook_id);
  const suffix = qs.toString() ? `?${qs}` : "";
  return api<ResolvedPrice>(`${SVC}/${id}/pricing${suffix}`);
}

export async function listServiceCategories(params?: {
  include_archived?: boolean;
}) {
  const qs = new URLSearchParams();
  if (params?.include_archived) qs.set("include_archived", "true");
  const suffix = qs.toString() ? `?${qs}` : "";
  return api<{ categories: ServiceCategory[] }>(`${CAT}${suffix}`);
}

export async function getServiceCategoryTree() {
  return api<{ tree: ServiceCategory[] }>(`${CAT}/tree`);
}

export async function createServiceCategory(body: Record<string, unknown>) {
  return api<ServiceCategory>(CAT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateServiceCategory(
  id: string,
  body: Record<string, unknown>,
) {
  return api<ServiceCategory>(`${CAT}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function archiveServiceCategory(
  id: string,
  body?: Record<string, unknown>,
) {
  return api<ServiceCategory>(`${CAT}/${id}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

export async function listPricebooks(params?: { include_archived?: boolean }) {
  const qs = new URLSearchParams();
  if (params?.include_archived) qs.set("include_archived", "true");
  const suffix = qs.toString() ? `?${qs}` : "";
  return api<{ pricebooks: Pricebook[] }>(`${PB}${suffix}`);
}

export async function getPricebook(id: string) {
  return api<Pricebook>(`${PB}/${id}`);
}

export async function createPricebook(body: Record<string, unknown>) {
  return api<Pricebook>(PB, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updatePricebook(id: string, body: Record<string, unknown>) {
  return api<Pricebook>(`${PB}/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function archivePricebook(id: string) {
  return api<Pricebook>(`${PB}/${id}`, { method: "DELETE" });
}

export async function createPricebookItem(
  pricebookId: string,
  body: Record<string, unknown>,
) {
  return api<PricebookItem>(`${PB}/${pricebookId}/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function archivePricebookItem(
  pricebookId: string,
  itemId: string,
) {
  return api<PricebookItem>(`${PB}/${pricebookId}/items/${itemId}`, {
    method: "DELETE",
  });
}

export async function createPricebookOverride(
  pricebookId: string,
  body: Record<string, unknown>,
) {
  return api<PricebookOverride>(`${PB}/${pricebookId}/overrides`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

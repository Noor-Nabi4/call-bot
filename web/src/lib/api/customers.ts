/** Typed helpers for Phase 4 Customer CRM admin APIs. */

import { api } from "./client";

export type CustomerStatus = "ACTIVE" | "INACTIVE";

export type CustomerTag = {
  id: string;
  name: string;
};

export type CustomerLocation = {
  id: string;
  customer_id: string;
  label?: string | null;
  address_line_1: string;
  address_line_2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  access_instructions?: string | null;
  is_primary: boolean;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type Customer = {
  id: string;
  name: string;
  display_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  address?: string | null;
  status: CustomerStatus | string;
  notes?: string | null;
  phones: string[];
  tags: CustomerTag[];
  locations?: CustomerLocation[];
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type CustomerNote = {
  id: string;
  customer_id: string;
  author_user_id?: string | null;
  body: string;
  created_at?: string | null;
};

export type CustomerTimelineEvent = {
  type: string;
  id: string;
  timestamp: string;
  title: string;
  summary?: string | null;
  source?: string | null;
  source_key?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type CustomerListParams = {
  q?: string;
  status?: string;
  include_archived?: boolean;
  limit?: number;
  cursor?: string;
};

export type CustomerListResponse = {
  customers: Customer[];
  next_cursor?: string | null;
  limit?: number;
};

export type CustomerCreateBody = {
  name?: string | null;
  display_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  status?: string | null;
  notes?: string | null;
  tags?: string[] | null;
};

export type CustomerUpdateBody = {
  name?: string | null;
  display_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  phone?: string | null;
  email?: string | null;
  address?: string | null;
  status?: string | null;
  notes?: string | null;
  tags?: string[] | null;
};

export type LocationCreateBody = {
  label?: string | null;
  address_line_1: string;
  address_line_2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  access_instructions?: string | null;
  is_primary?: boolean | null;
};

export type LocationUpdateBody = {
  label?: string | null;
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  access_instructions?: string | null;
  is_primary?: boolean | null;
};

const BASE = "/api/admin/crm/customers";

function listQuery(opts?: CustomerListParams): string {
  const params = new URLSearchParams();
  if (opts?.q) params.set("q", opts.q);
  if (opts?.status) params.set("status", opts.status);
  if (opts?.include_archived) params.set("include_archived", "true");
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.cursor) params.set("cursor", opts.cursor);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export function listCrmCustomers(opts?: CustomerListParams) {
  return api<CustomerListResponse>(`${BASE}${listQuery(opts)}`);
}

export function searchCrmCustomers(
  q: string,
  opts?: Omit<CustomerListParams, "q">,
) {
  const params = new URLSearchParams({ q });
  if (opts?.status) params.set("status", opts.status);
  if (opts?.include_archived) params.set("include_archived", "true");
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.cursor) params.set("cursor", opts.cursor);
  return api<CustomerListResponse>(`${BASE}/search?${params.toString()}`);
}

export function getCrmCustomer(customerId: string) {
  return api<{ customer: Customer }>(`${BASE}/${customerId}`);
}

export function createCrmCustomer(body: CustomerCreateBody) {
  return api<{ customer: Customer }>(BASE, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateCrmCustomer(customerId: string, body: CustomerUpdateBody) {
  return api<{ customer: Customer }>(`${BASE}/${customerId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function archiveCrmCustomer(customerId: string) {
  return api<{ customer: Customer }>(`${BASE}/${customerId}`, {
    method: "DELETE",
  });
}

export function restoreCrmCustomer(customerId: string) {
  return api<{ customer: Customer }>(`${BASE}/${customerId}/restore`, {
    method: "POST",
  });
}

export function listCrmCustomerLocations(
  customerId: string,
  opts?: { include_archived?: boolean },
) {
  const params = new URLSearchParams();
  if (opts?.include_archived) params.set("include_archived", "true");
  const qs = params.toString();
  return api<{ locations: CustomerLocation[] }>(
    `${BASE}/${customerId}/locations${qs ? `?${qs}` : ""}`,
  );
}

export function createCrmCustomerLocation(
  customerId: string,
  body: LocationCreateBody,
) {
  return api<{ location: CustomerLocation }>(`${BASE}/${customerId}/locations`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateCrmCustomerLocation(
  customerId: string,
  locationId: string,
  body: LocationUpdateBody,
) {
  return api<{ location: CustomerLocation }>(
    `${BASE}/${customerId}/locations/${locationId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export function setPrimaryCrmCustomerLocation(
  customerId: string,
  locationId: string,
) {
  return api<{ location: CustomerLocation }>(
    `${BASE}/${customerId}/locations/${locationId}/primary`,
    { method: "POST" },
  );
}

export function archiveCrmCustomerLocation(
  customerId: string,
  locationId: string,
) {
  return api<{ location: CustomerLocation }>(
    `${BASE}/${customerId}/locations/${locationId}`,
    { method: "DELETE" },
  );
}

export function addCrmCustomerTag(customerId: string, name: string) {
  return api<{ customer: Customer }>(`${BASE}/${customerId}/tags`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function removeCrmCustomerTag(customerId: string, tagId: string) {
  return api<{ customer: Customer }>(`${BASE}/${customerId}/tags/${tagId}`, {
    method: "DELETE",
  });
}

export function addCrmCustomerNote(customerId: string, body: string) {
  return api<{ note: CustomerNote }>(`${BASE}/${customerId}/notes`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export function getCrmCustomerTimeline(
  customerId: string,
  opts?: {
    event_type?: string;
    limit?: number;
    cursor?: string;
    since?: string;
    until?: string;
  },
) {
  const params = new URLSearchParams();
  if (opts?.event_type) params.set("event_type", opts.event_type);
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.cursor) params.set("cursor", opts.cursor);
  if (opts?.since) params.set("since", opts.since);
  if (opts?.until) params.set("until", opts.until);
  const qs = params.toString();
  return api<{
    items: CustomerTimelineEvent[];
    next_cursor?: string | null;
    limit?: number;
  }>(`${BASE}/${customerId}/timeline${qs ? `?${qs}` : ""}`);
}

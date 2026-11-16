import { api } from "@/lib/api";

export type MembershipPlan = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  monthly_price: string;
  annual_price: string;
  currency: string;
  priority_scheduling: boolean;
  discount_type: string | null;
  discount_value: string | null;
  included_services: Array<{
    id: string;
    service_id: string;
    included_quantity: number;
  }>;
};

export type CustomerMembership = {
  id: string;
  customer_id: string;
  plan_id: string;
  billing_interval: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  pending_plan_id: string | null;
  last_invoice_id: string | null;
  plan?: MembershipPlan;
  history?: Array<{
    id: string;
    event_type: string;
    from_status: string | null;
    to_status: string | null;
    effective_at: string;
  }>;
};

export async function listMembershipPlans(params?: {
  status?: string;
}): Promise<{ plans: MembershipPlan[] }> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  const q = qs.toString();
  return api(`/api/admin/crm/membership-plans${q ? `?${q}` : ""}`);
}

export async function createMembershipPlan(body: {
  name: string;
  monthly_price: string;
  annual_price: string;
  description?: string;
  priority_scheduling?: boolean;
  discount_type?: string | null;
  discount_value?: string | null;
  status?: string;
}): Promise<{ plan: MembershipPlan }> {
  return api("/api/admin/crm/membership-plans", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function activateMembershipPlan(
  planId: string
): Promise<{ plan: MembershipPlan }> {
  return api(`/api/admin/crm/membership-plans/${planId}/activate`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function listMemberships(params?: {
  customer_id?: string;
  status?: string;
  limit?: number;
}): Promise<{ memberships: CustomerMembership[] }> {
  const qs = new URLSearchParams();
  if (params?.customer_id) qs.set("customer_id", params.customer_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return api(`/api/admin/crm/memberships${q ? `?${q}` : ""}`);
}

export async function getCustomerMembership(
  customerId: string
): Promise<{ membership: CustomerMembership | null }> {
  return api(`/api/admin/crm/customers/${customerId}/membership`);
}

export async function subscribeMembership(
  customerId: string,
  body: {
    plan_id: string;
    billing_interval: string;
    create_payment_link?: boolean;
  },
  idempotencyKey?: string
): Promise<CustomerMembership & { payment?: { checkout_url?: string } }> {
  return api(`/api/admin/crm/customers/${customerId}/memberships`, {
    method: "POST",
    body: JSON.stringify(body),
    headers: idempotencyKey
      ? { "Idempotency-Key": idempotencyKey }
      : undefined,
  });
}

export async function cancelMembership(
  membershipId: string,
  immediate = false
): Promise<{ membership: CustomerMembership }> {
  return api(`/api/admin/crm/memberships/${membershipId}/cancel`, {
    method: "POST",
    body: JSON.stringify({ immediate }),
  });
}

export async function getMembership(
  membershipId: string
): Promise<{ membership: CustomerMembership }> {
  return api(`/api/admin/crm/memberships/${membershipId}`);
}

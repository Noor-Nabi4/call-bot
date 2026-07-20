import { api } from "./client";

export type TenantSubscription = {
  tenant_id: string;
  plan_key: string;
  status: string;
  stripe_customer_id: string;
  stripe_subscription_id: string | null;
  stripe_price_id: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  trial_end: string | null;
  is_entitled: boolean;
  entitlements?: {
    monthly_minutes: number;
    concurrent_calls: number;
    phone_numbers: number;
    team_users: number;
    knowledge_documents: number;
    dispatch_enabled: boolean;
    tech_mobile_enabled: boolean;
    advanced_handoff_enabled: boolean;
  } | null;
};

export function getSubscription() {
  return api<{ subscription: TenantSubscription | null }>("/billing/subscription");
}

export function createCheckout(plan_key?: string) {
  return api<{ checkout_url: string }>("/billing/checkout", {
    method: "POST",
    body: JSON.stringify(plan_key ? { plan_key } : {}),
  });
}

export function createPortal() {
  return api<{ portal_url: string }>("/billing/portal", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

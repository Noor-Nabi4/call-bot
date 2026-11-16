import { api } from "./client";

export type TenantSubscription = {
  tenant_id: string;
  plan_key: string;
  status: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  stripe_price_id: string | null;
  current_period_end: string | null;
  billing_period_start?: string | null;
  billing_period_end?: string | null;
  next_billing_at?: string | null;
  monthly_price_cents?: number | null;
  included_minutes?: number | null;
  included_minutes_consumed?: number;
  overage_rate_cents?: number | null;
  cancel_at_period_end: boolean;
  trial_end: string | null;
  is_entitled: boolean;
  billing_model?: string;
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

export type TenantUsage = {
  period_start: string;
  period_end: string;
  period_kind: string;
  plan_key: string | null;
  voice_seconds: number;
  voice_minutes: number;
  included_minutes: number | null;
  overage_minutes: number;
  overage_per_minute_cents: number | null;
  estimated_overage_cents: number | null;
  call_count: number;
  resources: {
    team_users: { used: number; limit: number | null };
    phone_numbers: { used: number; limit: number | null };
    knowledge_documents: { used: number; limit: number | null };
    concurrent_calls: { used: number; limit: number | null };
  };
};

export type WalletBalance = {
  wallet_id: string;
  tenant_id: string;
  currency: string;
  available_balance_cents: number;
  reserved_balance_cents: number;
  status: string;
  low_balance_cents: number;
  critical_balance_cents: number;
  auto_topup_enabled: boolean;
};

export type WalletTransaction = {
  id: string;
  transaction_type: string;
  amount_cents: number;
  signed_amount_cents: number;
  currency: string;
  balance_after_cents: number;
  reference_type: string | null;
  reference_id: string | null;
  description: string | null;
  created_at: string | null;
};

export function getSubscription() {
  return api<{ subscription: TenantSubscription | null }>("/billing/subscription");
}

export function getUsage() {
  return api<{ usage: TenantUsage }>("/billing/usage");
}

export function getWallet() {
  return api<{ wallet: WalletBalance }>("/billing/wallet");
}

export function getWalletTransactions(limit = 50) {
  return api<{ transactions: WalletTransaction[] }>(
    `/billing/wallet/transactions?limit=${limit}`,
  );
}

export function getBillingSummary() {
  return api<{
    subscription: TenantSubscription | null;
    usage: TenantUsage;
    wallet: WalletBalance;
  }>("/billing/summary");
}

export function createCheckout(plan_key?: string) {
  return api<{ checkout_url: string }>("/billing/checkout", {
    method: "POST",
    body: JSON.stringify(plan_key ? { plan_key } : {}),
  });
}

export function createWalletTopup(amount_cents: number) {
  return api<{ checkout_url: string; topup_id: string; amount_cents: number }>(
    "/billing/wallet/topups",
    {
      method: "POST",
      body: JSON.stringify({ amount_cents }),
    },
  );
}

export function subscribeFromWallet(plan_key?: string) {
  return api<{ subscription: TenantSubscription }>("/billing/subscribe", {
    method: "POST",
    body: JSON.stringify(plan_key ? { plan_key } : {}),
  });
}

export function changePlan(plan_key: string) {
  return api<{ subscription: TenantSubscription }>("/billing/change-plan", {
    method: "POST",
    body: JSON.stringify({ plan_key }),
  });
}

export function createPortal() {
  return api<{ portal_url: string }>("/billing/portal", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function formatCentsUsd(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

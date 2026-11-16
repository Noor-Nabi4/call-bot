/** Marketing site API helpers for signup / pricing. */

import { ApiError } from "@/lib/api/api-error";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type ApiDetail = { code?: string; message?: string } | string | undefined;

function detailMessage(detail: ApiDetail, fallback: string): string {
  if (typeof detail === "object" && detail?.message) return detail.message;
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

function detailCode(detail: ApiDetail): string | undefined {
  return typeof detail === "object" ? detail?.code : undefined;
}

export type PlanEntitlements = {
  monthly_minutes: number;
  concurrent_calls: number;
  phone_numbers: number;
  team_users: number;
  knowledge_documents: number;
  dispatch_enabled: boolean;
  tech_mobile_enabled: boolean;
  advanced_handoff_enabled: boolean;
};

export type Plan = {
  key: string;
  name: string;
  tagline: string;
  cta?: string;
  popular?: boolean;
  badge?: string;
  checkoutable?: boolean;
  features: string[];
  highlights?: string[];
  stripe_price_id: string | null;
  configured: boolean;
  unit_amount?: number | null;
  annual_amount?: number | null;
  currency?: string | null;
  interval?: string | null;
  overage_per_minute_cents?: number | null;
  entitlements?: PlanEntitlements | null;
};

export type PricingCatalog = {
  plans: Plan[];
  enterprise: Plan;
  trial: {
    days: number;
    voice_minutes: number;
    concurrent_calls: number;
    browser_voice_testing: boolean;
    credit_card_required: boolean;
    summary: string;
    phone_number_requirements: string[];
  };
  number_pricing: {
    connect_existing: { platform_fee: number; summary: string };
    platform_purchase: {
      us_local_monthly_cents: number;
      summary: string;
    };
  };
  add_ons: Array<{
    key: string;
    name: string;
    unit_amount: number | null;
    interval: string | null;
    currency: string;
    summary?: string;
  }>;
  pricing_model: string;
};

export async function fetchPricingCatalog(
  enrich = true,
): Promise<PricingCatalog> {
  const res = await fetch(
    `${API}/billing/plans?enrich=${enrich ? "true" : "false"}`,
    { cache: "no-store" },
  );
  if (!res.ok) {
    throw new Error("Could not load plans");
  }
  return (await res.json()) as PricingCatalog;
}

/** @deprecated Prefer fetchPricingCatalog */
export async function fetchPlans(enrich = true): Promise<Plan[]> {
  const catalog = await fetchPricingCatalog(enrich);
  return catalog.plans || [];
}

export type SignupFieldError = {
  code: string;
  message: string;
};

export type SignupValidateInput = {
  slug?: string;
  email?: string;
  plan_key?: string;
};

export type SignupValidateResult = {
  ok: boolean;
  errors: Partial<Record<keyof SignupValidateInput, SignupFieldError>>;
};

export async function validateSignup(
  fields: SignupValidateInput,
  options?: { signal?: AbortSignal },
): Promise<SignupValidateResult> {
  const body: SignupValidateInput = {};
  if (fields.slug !== undefined) body.slug = fields.slug;
  if (fields.email !== undefined) body.email = fields.email;
  if (fields.plan_key !== undefined) body.plan_key = fields.plan_key;

  const res = await fetch(`${API}/auth/signup/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "omit",
    cache: "no-store",
    signal: options?.signal,
    body: JSON.stringify(body),
  });
  const data = (await res.json().catch(() => ({}))) as SignupValidateResult & {
    detail?: ApiDetail;
  };
  if (!res.ok) {
    throw new ApiError(
      detailMessage(data.detail, "Could not validate signup details"),
      res.status,
      detailCode(data.detail),
    );
  }
  return {
    ok: Boolean(data.ok),
    errors: data.errors && typeof data.errors === "object" ? data.errors : {},
  };
}

export async function signup(body: {
  business_name: string;
  timezone: string;
  name: string;
  email: string;
  password: string;
  plan_key: string;
}): Promise<{ checkout_url: string; slug?: string }> {
  const res = await fetch(`${API}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  const data = (await res.json().catch(() => ({}))) as {
    checkout_url?: string;
    slug?: string;
    detail?: ApiDetail;
  };
  if (!res.ok) {
    throw new ApiError(
      detailMessage(data.detail, "Signup failed"),
      res.status,
      detailCode(data.detail),
    );
  }
  if (!data.checkout_url) {
    throw new ApiError("Checkout did not start", 502, "checkout_missing");
  }
  return { checkout_url: data.checkout_url, slug: data.slug };
}

export function formatMoney(
  amountCents: number | null | undefined,
  currency = "usd",
): string {
  if (amountCents == null) return "Custom";
  const amount = amountCents / 100;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.toUpperCase(),
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${amount} ${currency.toUpperCase()}`;
  }
}

export function formatPlanPrice(plan: Plan): string {
  return formatMoney(plan.unit_amount, plan.currency || "usd");
}

export function formatOverage(cents: number | null | undefined): string {
  if (cents == null) return "—";
  return `$${(cents / 100).toFixed(2)}/min`;
}

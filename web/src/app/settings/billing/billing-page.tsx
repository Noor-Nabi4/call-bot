"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { isOnboardingComplete, ONBOARDING_PATH } from "@/lib/onboarding";
import {
  BookOpen,
  CreditCard,
  Headphones,
  LayoutGrid,
  Phone,
  Users,
  Wrench,
  Zap,
} from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { billing as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  createCheckout,
  createPortal,
  formatWhen,
  getSubscription,
  getUsage,
  type TenantSubscription,
  type TenantUsage,
} from "@/lib/api";
import { UsageSummaryPanel } from "@/components/ops";
import {
  Button,
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  Surface,
  useToast,
} from "@/components/ui";

const CHECKOUT_ELIGIBLE = new Set([
  "incomplete",
  "incomplete_expired",
  "canceled",
  "unpaid",
]);

function planDisplayName(planKey: string): string {
  if (!planKey) return "—";
  return planKey.replace(/_/g, " ");
}

export default function BillingPage() {
  const router = useRouter();
  const { user, loading, forbidden } = useAuth({
    permission: "billing.read",
    allowIncompleteOnboarding: true,
  });
  const toast = useToast();
  const searchParams = useSearchParams();
  const checkoutSuccess = searchParams.get("checkout") === "success";

  const [subscription, setSubscription] = useState<TenantSubscription | null>(
    null,
  );
  const [usage, setUsage] = useState<TenantUsage | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);
  const [checkoutBusy, setCheckoutBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [subData, usageData] = await Promise.all([
      getSubscription(),
      getUsage(),
    ]);
    setSubscription(subData.subscription);
    setUsage(usageData.usage);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refresh()
        .catch((e) => setError(safeUserError(e, copy.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, refresh]);

  useEffect(() => {
    if (!user || !checkoutSuccess) return;
    if (subscription?.is_entitled) return;
    const id = window.setInterval(() => {
      refresh().catch(() => {
        /* keep polling */
      });
    }, 2500);
    return () => window.clearInterval(id);
  }, [user, checkoutSuccess, subscription?.is_entitled, refresh]);

  // After signup checkout, continue mandatory onboarding (not the dashboard).
  useEffect(() => {
    if (!user || !subscription?.is_entitled) return;
    if (isOnboardingComplete(user)) return;
    router.replace(
      checkoutSuccess ? `${ONBOARDING_PATH}?checkout=success` : ONBOARDING_PATH,
    );
  }, [user, subscription?.is_entitled, checkoutSuccess, router]);

  async function onPortal() {
    setPortalBusy(true);
    try {
      const { portal_url } = await createPortal();
      window.location.assign(portal_url);
    } catch (e) {
      toast.push(safeUserError(e, copy.portalFailed), "error");
      setPortalBusy(false);
    }
  }

  async function onCheckout() {
    setCheckoutBusy(true);
    try {
      const { checkout_url } = await createCheckout(
        subscription?.plan_key || undefined,
      );
      window.location.assign(checkout_url);
    } catch (e) {
      toast.push(safeUserError(e, copy.checkoutFailed), "error");
      setCheckoutBusy(false);
    }
  }

  if (loading || !user) {
    return <LoadingSkeleton rows={4} />;
  }

  if (forbidden && user) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  const awaitingWebhook = checkoutSuccess && !subscription?.is_entitled;
  const canCheckout =
    !subscription || CHECKOUT_ELIGIBLE.has(subscription.status);
  const entitlements = subscription?.entitlements;

  const limitRows = entitlements
    ? [
        {
          icon: Zap,
          label: copy.minutes,
          value: String(entitlements.monthly_minutes),
        },
        {
          icon: Headphones,
          label: copy.concurrent,
          value: String(entitlements.concurrent_calls),
        },
        {
          icon: Phone,
          label: copy.numbers,
          value: String(entitlements.phone_numbers),
        },
        {
          icon: Users,
          label: copy.users,
          value: String(entitlements.team_users),
        },
        {
          icon: BookOpen,
          label: copy.knowledge,
          value: String(entitlements.knowledge_documents),
        },
        {
          icon: LayoutGrid,
          label: copy.dispatch,
          value: entitlements.dispatch_enabled
            ? copy.featuresIncluded
            : copy.featuresNotIncluded,
          muted: !entitlements.dispatch_enabled,
        },
        {
          icon: Wrench,
          label: copy.techMobile,
          value: entitlements.tech_mobile_enabled
            ? copy.featuresIncluded
            : copy.featuresNotIncluded,
          muted: !entitlements.tech_mobile_enabled,
        },
      ]
    : [];

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          subscription ? (
            <div className="flex flex-wrap gap-2">
              {canCheckout ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onCheckout}
                  disabled={checkoutBusy}
                >
                  {checkoutBusy ? copy.startingCheckout : copy.completeCheckout}
                </Button>
              ) : null}
              <Button size="sm" onClick={onPortal} disabled={portalBusy}>
                <CreditCard className="size-3.5" aria-hidden />
                {portalBusy ? copy.managing : copy.manage}
              </Button>
            </div>
          ) : null
        }
      />

      {error ? (
        <ErrorState className="mt-4" title={copy.loadFailed} message={error} />
      ) : null}

      {fetching ? (
        <LoadingSkeleton className="mt-6" rows={5} />
      ) : (
        <div className="mt-6 space-y-5">
          {awaitingWebhook ? (
            <div className="rounded-[var(--radius-md)] border border-teal/30 bg-teal-soft/70 px-4 py-3">
              <p className="m-0 text-sm font-semibold text-ink">
                {copy.confirming}
              </p>
              <p className="mt-0.5 m-0 text-sm text-text-secondary">
                {copy.confirmingHint}
              </p>
            </div>
          ) : null}

          {subscription ? (
            <section className="ops-billing-hero overflow-hidden rounded-[var(--radius-lg)] text-white">
              <div className="relative px-5 py-6 sm:px-7 sm:py-7">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="m-0 text-[11px] font-medium tracking-[0.14em] text-white/55 uppercase">
                      {copy.plan}
                    </p>
                    <h2 className="mt-1 font-display text-3xl font-semibold tracking-tight capitalize sm:text-4xl">
                      {planDisplayName(subscription.plan_key)}
                    </h2>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <StatusPill status={subscription.status} />
                      {subscription.is_entitled ? (
                        <span className="text-xs text-teal-bright">
                          {copy.active}
                        </span>
                      ) : null}
                      {subscription.cancel_at_period_end ? (
                        <span className="text-xs text-amber-200">
                          {copy.cancelAtPeriodEnd}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="m-0 text-[11px] font-medium tracking-[0.12em] text-white/55 uppercase">
                      {copy.periodEnd}
                    </p>
                    <p className="mt-1 m-0 font-mono text-sm text-white/90">
                      {formatWhen(subscription.current_period_end)}
                    </p>
                  </div>
                </div>
              </div>
            </section>
          ) : (
            <EmptyState
              icon={<CreditCard className="size-8" />}
              title={copy.noSubscription}
              description={copy.noSubscriptionHint}
              action={
                <Button onClick={onCheckout} disabled={checkoutBusy}>
                  {checkoutBusy ? copy.startingCheckout : copy.completeCheckout}
                </Button>
              }
            />
          )}

          {usage ? (
            <UsageSummaryPanel usage={usage} className="ops-surface-rise" />
          ) : null}

          {limitRows.length > 0 ? (
            <Surface className="ops-surface-rise p-5">
              <h2 className="m-0 text-sm font-semibold text-ink">
                {copy.entitlements}
              </h2>
              <ul className="mt-4 m-0 grid list-none gap-3 p-0 sm:grid-cols-2 lg:grid-cols-3">
                {limitRows.map((row) => {
                  const Icon = row.icon;
                  return (
                    <li
                      key={row.label}
                      className="flex items-start gap-3 rounded-[var(--radius-md)] border border-border/80 bg-fog/60 px-3 py-3"
                    >
                      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-teal-soft text-teal">
                        <Icon className="size-4" aria-hidden />
                      </span>
                      <div className="min-w-0">
                        <p className="m-0 text-xs text-text-muted">{row.label}</p>
                        <p
                          className={
                            row.muted
                              ? "mt-0.5 m-0 text-sm text-text-muted"
                              : "mt-0.5 m-0 text-sm font-semibold text-ink"
                          }
                        >
                          {row.value}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </Surface>
          ) : null}
        </div>
      )}
    </AppShell>
  );
}

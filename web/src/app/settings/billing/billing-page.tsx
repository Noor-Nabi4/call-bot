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
  changePlan,
  createWalletTopup,
  formatCentsUsd,
  formatWhen,
  getSubscription,
  getUsage,
  getWallet,
  getWalletTransactions,
  subscribeFromWallet,
  type TenantSubscription,
  type TenantUsage,
  type WalletBalance,
  type WalletTransaction,
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
  const [wallet, setWallet] = useState<WalletBalance | null>(null);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [topupBusy, setTopupBusy] = useState<number | null>(null);
  const [subscribeBusy, setSubscribeBusy] = useState(false);
  const [planBusy, setPlanBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [subData, usageData, walletData, txnData] = await Promise.all([
      getSubscription(),
      getUsage(),
      getWallet(),
      getWalletTransactions(20),
    ]);
    setSubscription(subData.subscription);
    setUsage(usageData.usage);
    setWallet(walletData.wallet);
    setTransactions(txnData.transactions);
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

  async function onTopup(amountCents: number) {
    setTopupBusy(amountCents);
    try {
      const { checkout_url } = await createWalletTopup(amountCents);
      window.location.assign(checkout_url);
    } catch (e) {
      toast.push(safeUserError(e, "Could not start wallet top-up"), "error");
      setTopupBusy(null);
    }
  }

  async function onActivatePlan() {
    setSubscribeBusy(true);
    try {
      await subscribeFromWallet(subscription?.plan_key || undefined);
      await refresh();
      toast.push("Plan activated from wallet", "success");
    } catch (e) {
      toast.push(safeUserError(e, "Could not activate plan"), "error");
    } finally {
      setSubscribeBusy(false);
    }
  }

  async function onChangePlan(planKey: string) {
    setPlanBusy(planKey);
    try {
      await changePlan(planKey);
      await refresh();
      toast.push(`Plan updated to ${planDisplayName(planKey)}`, "success");
    } catch (e) {
      toast.push(safeUserError(e, "Could not change plan"), "error");
    } finally {
      setPlanBusy(null);
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
  const canActivate =
    !!subscription &&
    CHECKOUT_ELIGIBLE.has(subscription.status) &&
    (wallet?.available_balance_cents ?? 0) > 0;
  const canChangePlan =
    !!subscription &&
    (subscription.status === "active" || subscription.status === "trialing");
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
        description="USD wallet balance funds your plan and voice overage. Add funds anytime."
        actions={
          canActivate ? (
            <Button size="sm" disabled={subscribeBusy} onClick={onActivatePlan}>
              {subscribeBusy ? "Activating…" : "Activate plan"}
            </Button>
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

          {wallet ? (
            <Surface className="ops-surface-rise p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="m-0 text-[11px] font-medium tracking-[0.12em] text-text-muted uppercase">
                    USD wallet
                  </p>
                  <p className="mt-1 m-0 font-display text-3xl font-semibold text-ink">
                    {formatCentsUsd(wallet.available_balance_cents)}
                  </p>
                  <p className="mt-1 m-0 text-sm text-text-secondary">
                    Status: {wallet.status}
                    {wallet.available_balance_cents <= wallet.low_balance_cents
                      ? " · Low balance"
                      : ""}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {[1000, 2500, 5000, 10000, 25000].map((cents) => (
                    <Button
                      key={cents}
                      size="sm"
                      variant="secondary"
                      disabled={topupBusy !== null}
                      onClick={() => onTopup(cents)}
                    >
                      {topupBusy === cents
                        ? "Starting…"
                        : `Add ${formatCentsUsd(cents)}`}
                    </Button>
                  ))}
                  {canActivate ? (
                    <Button
                      size="sm"
                      disabled={subscribeBusy}
                      onClick={onActivatePlan}
                    >
                      {subscribeBusy ? "Activating…" : "Activate plan"}
                    </Button>
                  ) : null}
                </div>
              </div>
              {transactions.length > 0 ? (
                <ul className="mt-5 m-0 list-none space-y-2 border-t border-border/70 p-0 pt-4">
                  {transactions.map((txn) => (
                    <li
                      key={txn.id}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <span className="min-w-0 truncate text-text-secondary">
                        {txn.description || txn.reference_type || txn.transaction_type}
                      </span>
                      <span
                        className={
                          txn.signed_amount_cents >= 0
                            ? "font-mono text-teal"
                            : "font-mono text-ink"
                        }
                      >
                        {txn.signed_amount_cents >= 0 ? "+" : ""}
                        {formatCentsUsd(txn.signed_amount_cents)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Surface>
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
              description="Add funds to your wallet, then activate a plan from your balance."
            />
          )}

          {canChangePlan ? (
            <Surface className="ops-surface-rise p-5">
              <h2 className="m-0 text-sm font-semibold text-ink">Change plan</h2>
              <p className="mt-1 m-0 text-sm text-text-secondary">
                Upgrades debit the prorated difference now. Downgrades apply at
                the next billing period.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {(["starter", "growth", "pro"] as const).map((key) => (
                  <Button
                    key={key}
                    size="sm"
                    variant={
                      subscription?.plan_key === key ? "primary" : "secondary"
                    }
                    disabled={
                      planBusy !== null || subscription?.plan_key === key
                    }
                    onClick={() => onChangePlan(key)}
                  >
                    {planBusy === key
                      ? "Updating…"
                      : planDisplayName(key)}
                  </Button>
                ))}
              </div>
            </Surface>
          ) : null}

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

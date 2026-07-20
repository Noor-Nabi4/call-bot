"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { billing as copy } from "@/lib/copy";
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
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
} from "@/components/ui";

const CHECKOUT_ELIGIBLE = new Set([
  "incomplete",
  "incomplete_expired",
  "canceled",
  "unpaid",
]);

export default function BillingPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
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

  // Poll after Checkout success until webhook confirms entitlement.
  useEffect(() => {
    if (!user || !checkoutSuccess) return;
    if (subscription?.is_entitled) return;
    let cancelled = false;
    const id = window.setInterval(() => {
      refresh().catch(() => {
        /* keep polling; surface errors from initial load */
      });
    }, 2500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      void cancelled;
    };
  }, [user, checkoutSuccess, subscription?.is_entitled, refresh]);

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

  const awaitingWebhook =
    checkoutSuccess && !subscription?.is_entitled;
  const canCheckout =
    !subscription || CHECKOUT_ELIGIBLE.has(subscription.status);

  return (
    <AppShell user={user}>
      <PageHeader title={copy.title} description={copy.description} />

      {error ? (
        <ErrorState className="mt-4" title={copy.loadFailed} message={error} />
      ) : null}

      {fetching ? (
        <LoadingSkeleton className="mt-6" rows={3} />
      ) : (
        <div className="mt-6 grid max-w-2xl gap-4">
          {awaitingWebhook ? (
            <Surface className="border-teal/40 bg-teal-soft p-4">
              <p className="m-0 text-sm font-semibold text-ink">{copy.confirming}</p>
              <p className="mt-1 m-0 text-sm text-text-secondary">
                {copy.confirmingHint}
              </p>
            </Surface>
          ) : null}

          {!subscription ? (
            <EmptyState
              title={copy.noSubscription}
              description={copy.noSubscriptionHint}
              action={
                <Button onClick={onCheckout} disabled={checkoutBusy}>
                  {checkoutBusy ? copy.startingCheckout : copy.completeCheckout}
                </Button>
              }
            />
          ) : (
            <Surface className="p-5">
              <dl className="m-0 grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.plan}
                  </dt>
                  <dd className="mt-1 m-0 text-lg font-semibold capitalize text-ink">
                    {subscription.plan_key}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.status}
                  </dt>
                  <dd className="mt-1 m-0 font-mono text-sm uppercase text-ink">
                    {subscription.status}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.periodEnd}
                  </dt>
                  <dd className="mt-1 m-0 text-sm text-ink">
                    {formatWhen(subscription.current_period_end)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.cancelAtPeriodEnd}
                  </dt>
                  <dd className="mt-1 m-0 text-sm text-ink">
                    {subscription.cancel_at_period_end ? "Yes" : "No"}
                  </dd>
                </div>
              </dl>

              {subscription.entitlements ? (
                <div className="mt-6 border-t border-border pt-4">
                  <p className="m-0 text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.entitlements}
                  </p>
                  <dl className="mt-3 m-0 grid gap-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-text-muted">{copy.minutes}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.monthly_minutes}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.concurrent}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.concurrent_calls}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.numbers}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.phone_numbers}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.users}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.team_users}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.knowledge}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.knowledge_documents}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.dispatch}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.dispatch_enabled
                          ? "Included"
                          : "Not included"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.techMobile}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {subscription.entitlements.tech_mobile_enabled
                          ? "Included"
                          : "Not included"}
                      </dd>
                    </div>
                  </dl>
                </div>
              ) : null}

              {usage ? (
                <div className="mt-6 border-t border-border pt-4">
                  <p className="m-0 text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.usage}
                  </p>
                  <p className="mt-1 m-0 text-xs text-text-secondary">
                    {copy.usageHint}
                  </p>
                  <dl className="mt-3 m-0 grid gap-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-text-muted">
                        {copy.minutesUsed}
                      </dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {usage.voice_minutes}
                        {usage.included_minutes != null
                          ? ` / ${usage.included_minutes}`
                          : ""}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.calls}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {usage.call_count}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-text-muted">{copy.overage}</dt>
                      <dd className="m-0 text-sm font-medium text-ink">
                        {usage.overage_minutes} min
                        {usage.estimated_overage_cents != null
                          ? ` ($${(usage.estimated_overage_cents / 100).toFixed(2)})`
                          : ""}
                      </dd>
                    </div>
                  </dl>
                  <p className="mt-4 m-0 text-xs font-medium uppercase tracking-wide text-text-muted">
                    {copy.resources}
                  </p>
                  <dl className="mt-3 m-0 grid gap-3 sm:grid-cols-2">
                    {(
                      [
                        ["users", usage.resources.team_users],
                        ["numbers", usage.resources.phone_numbers],
                        ["knowledge", usage.resources.knowledge_documents],
                        ["concurrent", usage.resources.concurrent_calls],
                      ] as const
                    ).map(([labelKey, slot]) => (
                      <div key={labelKey}>
                        <dt className="text-xs text-text-muted">
                          {copy[labelKey]}
                        </dt>
                        <dd className="m-0 text-sm font-medium text-ink">
                          {slot.used}
                          {slot.limit != null ? ` / ${slot.limit}` : ""}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </div>
              ) : null}

              {subscription.is_entitled ? (
                <p className="mt-4 m-0 text-sm text-text-secondary">{copy.active}</p>
              ) : null}

              <div className="mt-6 flex flex-wrap gap-3">
                <Button onClick={onPortal} disabled={portalBusy}>
                  {portalBusy ? copy.managing : copy.manage}
                </Button>
                {canCheckout ? (
                  <Button
                    variant="secondary"
                    onClick={onCheckout}
                    disabled={checkoutBusy}
                  >
                    {checkoutBusy
                      ? copy.startingCheckout
                      : copy.completeCheckout}
                  </Button>
                ) : null}
              </div>
            </Surface>
          )}
        </div>
      )}
    </AppShell>
  );
}

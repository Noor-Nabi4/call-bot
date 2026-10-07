"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  cancelMembership,
  getMembership,
  type CustomerMembership,
} from "@/lib/api/memberships";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function MembershipDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const [row, setRow] = useState<CustomerMembership | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await getMembership(id);
      setRow(res.membership);
    } catch (err) {
      setError(safeUserError(err));
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCancel() {
    if (
      !window.confirm(
        "Cancel this membership at the end of the current billing period?"
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await cancelMembership(id, false);
      setRow(res.membership);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Membership"
        description="Subscription status, period, and history."
      />
      <p className="mb-4">
        <Link href="/crm/memberships" className="underline-offset-2 hover:underline">
          ← Memberships
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {!row && !error ? <LoadingSkeleton /> : null}
      {row ? (
        <div className="space-y-4 max-w-xl">
          <div className="flex items-center gap-3">
            <StatusPill status={row.status} />
            {row.cancel_at_period_end ? (
              <span className="text-sm text-muted-foreground">
                Cancels at period end
              </span>
            ) : null}
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <dt>Customer</dt>
            <dd>
              <Link
                href={`/customers/${row.customer_id}`}
                className="underline-offset-2 hover:underline"
              >
                {row.customer_id.slice(0, 8)}
              </Link>
            </dd>
            <dt>Plan</dt>
            <dd>{row.plan?.name || row.plan_id.slice(0, 8)}</dd>
            <dt>Billing</dt>
            <dd>{row.billing_interval}</dd>
            <dt>Period</dt>
            <dd>
              {new Date(row.current_period_start).toLocaleDateString()} –{" "}
              {new Date(row.current_period_end).toLocaleDateString()}
            </dd>
            <dt>Invoice</dt>
            <dd>
              {row.last_invoice_id ? (
                <Link
                  href={`/crm/invoices/${row.last_invoice_id}`}
                  className="underline-offset-2 hover:underline"
                >
                  View invoice
                </Link>
              ) : (
                "—"
              )}
            </dd>
          </dl>
          {row.status === "ACTIVE" || row.status === "PENDING" ? (
            <Button type="button" onClick={onCancel} disabled={busy}>
              Cancel at period end
            </Button>
          ) : null}
          {row.history && row.history.length > 0 ? (
            <div>
              <h3 className="font-medium mb-2">History</h3>
              <ul className="space-y-1 text-sm">
                {row.history.map((h) => (
                  <li key={h.id}>
                    {h.event_type} · {new Date(h.effective_at).toLocaleString()}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}

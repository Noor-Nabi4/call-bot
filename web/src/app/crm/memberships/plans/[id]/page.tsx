"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { api } from "@/lib/api";
import type { MembershipPlan } from "@/lib/api/memberships";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function MembershipPlanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: authLoading } = useAuth();
  const [plan, setPlan] = useState<MembershipPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api<{ plan: MembershipPlan }>(
        `/api/admin/crm/membership-plans/${id}`
      );
      setPlan(res.plan);
    } catch (err) {
      setError(safeUserError(err));
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader title="Membership plan" description="Pricing and benefits." />
      <p className="mb-4">
        <Link href="/crm/memberships" className="underline-offset-2 hover:underline">
          ← Memberships
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {!plan && !error ? <LoadingSkeleton /> : null}
      {plan ? (
        <dl className="grid max-w-xl grid-cols-2 gap-3 text-sm">
          <dt>Name</dt>
          <dd className="font-medium">{plan.name}</dd>
          <dt>Status</dt>
          <dd>
            <StatusPill status={plan.status} />
          </dd>
          <dt>Monthly</dt>
          <dd>
            {plan.currency} {plan.monthly_price}
          </dd>
          <dt>Annual</dt>
          <dd>
            {plan.currency} {plan.annual_price}
          </dd>
          <dt>Priority scheduling</dt>
          <dd>{plan.priority_scheduling ? "Yes" : "No"}</dd>
          <dt>Discount</dt>
          <dd>
            {plan.discount_type
              ? `${plan.discount_type} ${plan.discount_value}`
              : "—"}
          </dd>
          <dt>Included services</dt>
          <dd>
            {plan.included_services.length === 0
              ? "—"
              : plan.included_services
                  .map((s) => `${s.service_id.slice(0, 8)} × ${s.included_quantity}`)
                  .join(", ")}
          </dd>
        </dl>
      ) : null}
    </AppShell>
  );
}

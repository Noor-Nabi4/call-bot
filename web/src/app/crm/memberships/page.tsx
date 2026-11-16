"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  activateMembershipPlan,
  createMembershipPlan,
  listMembershipPlans,
  listMemberships,
  type CustomerMembership,
  type MembershipPlan,
} from "@/lib/api/memberships";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  type DataTableColumn,
} from "@/components/ui";

export default function MembershipsPage() {
  const { user, loading: authLoading } = useAuth();
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [memberships, setMemberships] = useState<CustomerMembership[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [monthly, setMonthly] = useState("49.00");
  const [annual, setAnnual] = useState("490.00");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, m] = await Promise.all([
        listMembershipPlans(),
        listMemberships({ limit: 50 }),
      ]);
      setPlans(p.plans);
      setMemberships(m.memberships);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await createMembershipPlan({
        name,
        monthly_price: monthly,
        annual_price: annual,
        status: "DRAFT",
      });
      await activateMembershipPlan(created.plan.id);
      setName("");
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  const planColumns: DataTableColumn<MembershipPlan>[] = [
    {
      id: "name",
      header: "Plan",
      cell: (row) => (
        <Link
          href={`/crm/memberships/plans/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.name}
        </Link>
      ),
    },
    {
      id: "monthly",
      header: "Monthly",
      cell: (row) => `${row.currency} ${row.monthly_price}`,
    },
    {
      id: "annual",
      header: "Annual",
      cell: (row) => `${row.currency} ${row.annual_price}`,
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
  ];

  const memberColumns: DataTableColumn<CustomerMembership>[] = [
    {
      id: "id",
      header: "Membership",
      cell: (row) => (
        <Link
          href={`/crm/memberships/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.id.slice(0, 8)}
        </Link>
      ),
    },
    {
      id: "customer",
      header: "Customer",
      cell: (row) => (
        <Link
          href={`/customers/${row.customer_id}`}
          className="underline-offset-2 hover:underline"
        >
          {row.customer_id.slice(0, 8)}
        </Link>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
    {
      id: "interval",
      header: "Billing",
      cell: (row) => row.billing_interval,
    },
    {
      id: "period",
      header: "Period end",
      cell: (row) =>
        row.current_period_end
          ? new Date(row.current_period_end).toLocaleDateString()
          : "—",
    },
  ];

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
        title="Memberships"
        description="Plans, customer subscriptions, and billing via invoices."
      />
      {error ? <ErrorState message={error} /> : null}
      {loading ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-10">
          <section className="space-y-4">
            <h2 className="text-lg font-semibold">Plans</h2>
            <form
              onSubmit={onCreate}
              className="grid max-w-xl gap-3 sm:grid-cols-3"
            >
              <Field label="Name">
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </Field>
              <Field label="Monthly">
                <Input
                  value={monthly}
                  onChange={(e) => setMonthly(e.target.value)}
                  required
                />
              </Field>
              <Field label="Annual">
                <Input
                  value={annual}
                  onChange={(e) => setAnnual(e.target.value)}
                  required
                />
              </Field>
              <div className="sm:col-span-3">
                <Button type="submit" disabled={busy || !name.trim()}>
                  Create & activate plan
                </Button>
              </div>
            </form>
            {plans.length === 0 ? (
              <EmptyState title="No membership plans yet" />
            ) : (
              <DataTable columns={planColumns} rows={plans} />
            )}
          </section>
          <section className="space-y-4">
            <h2 className="text-lg font-semibold">Customer memberships</h2>
            {memberships.length === 0 ? (
              <EmptyState title="No memberships yet" />
            ) : (
              <DataTable columns={memberColumns} rows={memberships} />
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}

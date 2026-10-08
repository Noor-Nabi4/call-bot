"use client";

import { AppShell } from "@/components/shell";
import { UsageCostPanel } from "@/components/ops/usage-cost-panel";
import { useAuth } from "@/lib/use-auth";
import { ForbiddenState, LoadingSkeleton, PageHeader } from "@/components/ui";

export default function OrganizationUsagePage() {
  const { user, loading, forbidden } = useAuth({ permission: "billing.read" });

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (forbidden && user) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
        <PageHeader
          title="Usage"
          description="Track your organization's consumption and plan limits."
        />
        <UsageCostPanel />
      </div>
    </AppShell>
  );
}

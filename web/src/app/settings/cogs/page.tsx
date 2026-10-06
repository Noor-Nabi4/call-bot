"use client";

import { AppShell } from "@/components/shell";
import { CogsDashboard } from "@/components/ops/cogs-dashboard";
import { useAuth } from "@/lib/use-auth";
import {
  ForbiddenState,
  LoadingSkeleton,
} from "@/components/ui";

export default function CogsPage() {
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
      <CogsDashboard />
    </AppShell>
  );
}

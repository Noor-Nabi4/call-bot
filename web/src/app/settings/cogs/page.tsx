"use client";

import { AppShell } from "@/components/shell";
import { CogsDashboard } from "@/components/ops/cogs-dashboard";
import { useAuth } from "@/lib/use-auth";
import { LoadingSkeleton } from "@/components/ui";

export default function CogsPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <CogsDashboard />
    </AppShell>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { ForbiddenState, LoadingSkeleton } from "@/components/ui";

/**
 * Former org COGS route — platform financials are not customer-facing.
 * Organization Owners are redirected to Usage; they never receive COGS data.
 */
export default function CogsRedirectPage() {
  const router = useRouter();
  const { user, loading, forbidden } = useAuth({ permission: "billing.read" });

  useEffect(() => {
    if (!loading && user && !forbidden) {
      router.replace("/settings/usage");
    }
  }, [loading, user, forbidden, router]);

  if (loading || !user) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-8">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  if (forbidden) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <LoadingSkeleton rows={4} />
      </div>
    </AppShell>
  );
}

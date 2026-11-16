"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { completeOAuthCallback } from "@/lib/api/integrations";
import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";
import { ErrorState, LoadingSkeleton, Surface } from "@/components/ui";

/**
 * OAuth redirect landing. Provider + state + code come from query string.
 * Tenant is never taken from the callback — bound via OAuth state server-side.
 */
function CallbackInner() {
  const { user, loading, forbidden } = useAuth({
    permission: "integrations.connect",
  });
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || forbidden) return;
    const code = params.get("code");
    const state = params.get("state");
    const provider = params.get("provider");
    if (!code || !state || !provider) {
      setError("Missing OAuth callback parameters");
      return;
    }
    let cancelled = false;
    void completeOAuthCallback(provider, state, code)
      .then(() => {
        if (!cancelled) router.replace("/settings/integrations");
      })
      .catch((e) => {
        if (!cancelled) setError(safeUserError(e, errors.saveFailed));
      });
    return () => {
      cancelled = true;
    };
  }, [user, forbidden, params, router]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={3} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      {error ? (
        <ErrorState
          message={error}
          onRetry={() => router.replace("/settings/integrations")}
        />
      ) : (
        <Surface className="p-6 text-sm text-text-secondary">
          Completing connection…
        </Surface>
      )}
    </AppShell>
  );
}

export default function IntegrationsCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={3} />
        </div>
      }
    >
      <CallbackInner />
    </Suspense>
  );
}

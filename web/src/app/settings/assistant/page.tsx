"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell";
import { ForbiddenState, LoadingSkeleton } from "@/components/ui";
import { useAuth } from "@/lib/use-auth";
import { listAgentProfiles } from "@/lib/api";

/** Legacy assistant settings → Agents hub (default profile when available). */
export default function AssistantRedirectPage() {
  const { user, loading, forbidden } = useAuth({ permission: "ai.configure" });
  const router = useRouter();

  useEffect(() => {
    if (!user || forbidden) return;
    listAgentProfiles()
      .then((data) => {
        const def = data.profiles.find((p) => p.is_default) || data.profiles[0];
        router.replace(def ? `/agents/${def.id}` : "/agents");
      })
      .catch(() => router.replace("/agents"));
  }, [user, forbidden, router]);

  if (loading || !user) {
    return (
      <div className="p-6">
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
    <div className="p-6">
      <LoadingSkeleton rows={4} />
    </div>
  );
}

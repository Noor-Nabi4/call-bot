"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoadingSkeleton } from "@/components/ui";
import { useAuth } from "@/lib/use-auth";
import { listAgentProfiles } from "@/lib/api";

/** Legacy assistant settings → Agents hub (default profile when available). */
export default function AssistantRedirectPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const router = useRouter();

  useEffect(() => {
    if (!user) return;
    listAgentProfiles()
      .then((data) => {
        const def = data.profiles.find((p) => p.is_default) || data.profiles[0];
        router.replace(def ? `/agents/${def.id}` : "/agents");
      })
      .catch(() => router.replace("/agents"));
  }, [user, router]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  return (
    <div className="p-6">
      <LoadingSkeleton rows={4} />
    </div>
  );
}

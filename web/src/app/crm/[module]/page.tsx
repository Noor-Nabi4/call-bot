"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { LoadingSkeleton, PageHeader, Surface } from "@/components/ui";

/**
 * Placeholder for CRM modules without a shipped transactional domain.
 * No mock records — configuration-only until Phase 4 gate closes.
 */
export default function CrmModulePlaceholderPage() {
  const params = useParams<{ module?: string }>();
  const moduleKey = String(params.module || "").toUpperCase();
  const { user, loading } = useAuth({ permission: "organization.read" });

  if (loading || !user) {
    return <LoadingSkeleton rows={4} />;
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={moduleKey || "CRM module"}
        description="Not yet available — this module can be enabled in CRM configuration, but transactional records are not shipped until Phase 4."
      />
      <Surface className="space-y-3 p-6 text-sm text-text-muted">
        <p>
          Module key: <code className="text-text-primary">{moduleKey}</code>
        </p>
        <p>
          No sample or mock data is shown here. Configure modules under{" "}
          <Link href="/settings/crm" className="text-accent hover:underline">
            Settings → CRM modules
          </Link>
          , or use custom objects for organization-defined entities.
        </p>
      </Surface>
    </AppShell>
  );
}

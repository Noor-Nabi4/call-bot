"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { LoadingSkeleton, PageHeader, Surface } from "@/components/ui";

/** Fallback page for CRM modules that are enabled but not yet live. */
export default function CrmModulePlaceholderPage() {
  const params = useParams<{ module?: string }>();
  const moduleKey = String(params.module || "").replace(/_/g, " ");
  const title = moduleKey
    ? moduleKey.replace(/\b\w/g, (c) => c.toUpperCase())
    : "CRM module";
  const { user, loading } = useAuth({ permission: "organization.read" });

  if (loading || !user) {
    return <LoadingSkeleton rows={4} />;
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={title}
        description="This area isn’t available yet for your workspace."
      />
      <Surface className="space-y-3 p-6 text-sm text-text-secondary">
        <p>
          You can manage which CRM modules are enabled under{" "}
          <Link href="/settings/crm" className="text-accent hover:underline">
            Settings → CRM modules
          </Link>
          , or use custom objects for organization-defined records.
        </p>
      </Surface>
    </AppShell>
  );
}

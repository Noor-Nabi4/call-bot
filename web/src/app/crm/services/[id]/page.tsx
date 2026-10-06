"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  archiveService,
  getService,
  getServicePricing,
  restoreService,
  type ResolvedPrice,
  type ServiceRow,
} from "@/lib/api/services";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function ServiceDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [service, setService] = useState<ServiceRow | null>(null);
  const [pricing, setPricing] = useState<ResolvedPrice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [svc, price] = await Promise.all([
        getService(id),
        getServicePricing(id).catch(() => null),
      ]);
      setService(svc);
      setPricing(price);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onArchive() {
    setBusy(true);
    try {
      await archiveService(id);
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRestore() {
    setBusy(true);
    try {
      await restoreService(id);
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={service?.name || "Service"}
        description="Service detail and resolved pricing."
        actions={
          <Link href="/crm/services">
            <Button variant="secondary">Back</Button>
          </Link>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading || !service ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="grid max-w-2xl gap-4">
          <dl className="grid gap-2 text-sm">
            <div>
              <dt className="text-text-muted">Code</dt>
              <dd>{service.code || "—"}</dd>
            </div>
            <div>
              <dt className="text-text-muted">Category</dt>
              <dd>{service.category_name || "—"}</dd>
            </div>
            <div>
              <dt className="text-text-muted">Duration</dt>
              <dd>
                {service.duration_minutes != null
                  ? `${service.duration_minutes} minutes`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">Base price</dt>
              <dd>{service.base_price ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-text-muted">Cost</dt>
              <dd>{service.cost ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-text-muted">Pricing type</dt>
              <dd>{service.pricing_type}</dd>
            </div>
            <div>
              <dt className="text-text-muted">Status</dt>
              <dd>
                <StatusPill status={service.status} />
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">Description</dt>
              <dd className="whitespace-pre-wrap">
                {service.description || "—"}
              </dd>
            </div>
          </dl>

          {pricing ? (
            <section className="rounded-lg border border-border p-4">
              <h2 className="mb-2 font-semibold">Effective price</h2>
              <p className="text-sm">
                {pricing.price ?? "Quote required"} ({pricing.pricing_type})
              </p>
              <p className="text-xs text-text-muted">
                Source: {pricing.source}
                {pricing.pricebook_name
                  ? ` · ${pricing.pricebook_name}`
                  : ""}
              </p>
            </section>
          ) : null}

          <div className="flex gap-2">
            {service.archived_at ? (
              <Button type="button" disabled={busy} onClick={() => void onRestore()}>
                Restore
              </Button>
            ) : (
              <Button
                type="button"
                variant="danger"
                disabled={busy}
                onClick={() => void onArchive()}
              >
                Archive
              </Button>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}

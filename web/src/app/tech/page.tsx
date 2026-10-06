"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Briefcase,
  MapPin,
  Navigation,
} from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  formatWhen,
  listJobs,
  pingLocation,
  type Job,
} from "@/lib/api";
import { deriveUrgency } from "@/lib/schedule";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/use-auth";
import { errors, tech as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  MetricSummary,
  PageHeader,
  StatusPill,
  Surface,
  urgencyEdgeClass,
} from "@/components/ui";

export default function TechHomePage() {
  const { user, loading, forbidden, isTechShell } = useAuth({
    permission: "jobs.read",
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [locMsg, setLocMsg] = useState<string | null>(null);
  const [locBusy, setLocBusy] = useState(false);
  const [fetching, setFetching] = useState(true);

  const refresh = useCallback(async () => {
    const data = await listJobs();
    setJobs(
      data.jobs.filter((j) =>
        ["scheduled", "dispatched", "in_progress"].includes(j.status),
      ),
    );
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refresh()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    const id = setInterval(() => {
      refresh().catch(() => undefined);
    }, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [user, refresh]);

  const sorted = useMemo(
    () =>
      [...jobs].sort((a, b) => {
        const ta = a.scheduled_starts_at
          ? new Date(a.scheduled_starts_at).getTime()
          : Infinity;
        const tb = b.scheduled_starts_at
          ? new Date(b.scheduled_starts_at).getTime()
          : Infinity;
        return ta - tb;
      }),
    [jobs],
  );

  const todayCount = useMemo(
    () =>
      sorted.filter((j) => deriveUrgency(j.scheduled_starts_at) === "today")
        .length,
    [sorted],
  );

  const nextJob = sorted[0] ?? null;
  const isTech = isTechShell;

  async function onPingLocation() {
    setLocMsg(null);
    setLocBusy(true);
    if (!navigator.geolocation) {
      setLocMsg("Geolocation not available on this device.");
      setLocBusy(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await pingLocation(pos.coords.latitude, pos.coords.longitude);
          setLocMsg("Location updated");
        } catch (e) {
          setLocMsg(
            safeUserError(e, "We could not update your location. Please try again."),
          );
        } finally {
          setLocBusy(false);
        }
      },
      () => {
        setLocMsg("Location permission denied — enable in browser settings.");
        setLocBusy(false);
      },
    );
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
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
      <PageHeader
        title={copy.title}
        description={copy.description}
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching && jobs.length === 0 ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <>
          <MetricSummary
            items={[
              { label: "Active", value: sorted.length },
              { label: "Today", value: todayCount },
              {
                label: "In progress",
                value: sorted.filter((j) => j.status === "in_progress").length,
              },
            ]}
            className="lg:grid-cols-3"
          />

          {nextJob ? (
            <Surface
              className={cn(
                "mb-4 border-l-4 p-4",
                urgencyEdgeClass(nextJob.scheduled_starts_at),
              )}
            >
              <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
                Next up
              </p>
              <div className="mt-2 flex items-start justify-between gap-3">
                <div>
                  <p className="font-mono text-xs text-text-muted">
                    {nextJob.reference_code}
                  </p>
                  <p className="text-lg font-semibold text-text-primary">
                    {nextJob.service_type}
                  </p>
                  <p className="text-sm text-text-secondary">
                    {nextJob.customer?.name}
                  </p>
                  <p className="text-sm text-text-muted">
                    {formatWhen(nextJob.scheduled_starts_at)}
                  </p>
                </div>
                <StatusPill status={nextJob.status} />
              </div>
              <Link href={`/tech/jobs/${nextJob.id}`} className="mt-4 block">
                <Button size="lg" className="w-full">
                  Open job
                </Button>
              </Link>
            </Surface>
          ) : null}

          <ul className="space-y-3">
            {sorted.map((job) => (
              <li key={job.id}>
                <Link
                  href={`/tech/jobs/${job.id}`}
                  className={cn(
                    "block rounded-lg border border-border border-l-4 bg-surface p-4 transition-colors hover:border-brand/30 active:bg-surface-muted",
                    urgencyEdgeClass(job.scheduled_starts_at),
                    isTech && "min-h-[5.5rem]",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-text-muted">
                        {job.reference_code}
                      </p>
                      <p className="text-base font-semibold text-text-primary">
                        {job.service_type}
                      </p>
                      <p className="text-sm text-text-secondary">
                        {job.customer?.name}
                      </p>
                      {job.customer?.address ? (
                        <p className="mt-1 flex items-start gap-1 text-xs text-text-muted">
                          <MapPin className="mt-0.5 size-3 shrink-0" aria-hidden />
                          <span className="line-clamp-2">{job.customer.address}</span>
                        </p>
                      ) : null}
                      <p className="mt-1 text-sm text-text-muted">
                        {formatWhen(job.scheduled_starts_at)}
                      </p>
                    </div>
                    <StatusPill status={job.status} />
                  </div>
                </Link>
              </li>
            ))}
            {sorted.length === 0 && (
              <EmptyState
                icon={<Briefcase className="size-8" />}
                title={copy.empty}
                description={copy.emptyHint}
              />
            )}
          </ul>
        </>
      )}

      {isTech ? (
        <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur-[2px] lg:static lg:mt-6 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
          <Button
            size="lg"
            variant="secondary"
            className="w-full"
            onClick={onPingLocation}
            disabled={locBusy}
          >
            <Navigation className="size-4" aria-hidden />
            {locBusy ? "Sharing location…" : "Share location"}
          </Button>
          {locMsg ? (
            <p className="mt-2 text-center text-xs text-text-muted">{locMsg}</p>
          ) : (
            <p className="mt-2 text-center text-xs text-text-muted">
              Share your location so dispatch can track field progress.
            </p>
          )}
        </div>
      ) : null}
    </AppShell>
  );
}

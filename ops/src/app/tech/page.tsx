"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell, StatusPill } from "@/components/shell";
import {
  formatWhen,
  listJobs,
  pingLocation,
  type Job,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

export default function TechHomePage() {
  const { user, loading } = useAuth({
    roles: ["technician", "admin"],
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [locMsg, setLocMsg] = useState<string | null>(null);

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
    refresh().catch((e) => setError(e.message));
    const id = setInterval(() => {
      refresh().catch(() => undefined);
    }, 5000);
    return () => clearInterval(id);
  }, [user, refresh]);

  async function onPingLocation() {
    setLocMsg(null);
    if (!navigator.geolocation) {
      setLocMsg("Geolocation not available");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          await pingLocation(pos.coords.latitude, pos.coords.longitude);
          setLocMsg("Location updated");
        } catch (e) {
          setLocMsg(e instanceof Error ? e.message : "Location failed");
        }
      },
      () => setLocMsg("Permission denied"),
    );
  }

  if (loading || !user) {
    return <p className="p-6 text-ink-muted">Loading…</p>;
  }

  return (
    <AppShell user={user}>
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">My jobs</h2>
          <p className="text-sm text-ink-muted">
            Today&apos;s assigned field work.
          </p>
        </div>
        {user.role === "technician" && (
          <button
            type="button"
            onClick={onPingLocation}
            className="rounded border border-line bg-panel px-3 py-1.5 text-sm"
          >
            Share location
          </button>
        )}
      </div>
      {error && <p className="mb-2 text-sm text-danger">{error}</p>}
      {locMsg && <p className="mb-2 text-sm text-ink-muted">{locMsg}</p>}

      <ul className="space-y-3">
        {jobs.map((job) => (
          <li key={job.id}>
            <Link
              href={`/tech/jobs/${job.id}`}
              className="block rounded border border-line bg-panel p-4 text-ink"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-mono text-xs text-ink-muted">
                    {job.reference_code}
                  </p>
                  <p className="text-lg font-semibold">{job.service_type}</p>
                  <p className="text-sm text-ink-muted">
                    {job.customer?.name}
                    {job.customer?.address ? ` · ${job.customer.address}` : ""}
                  </p>
                  <p className="text-sm text-ink-muted">
                    {formatWhen(job.scheduled_starts_at)}
                  </p>
                </div>
                <StatusPill status={job.status} />
              </div>
            </Link>
          </li>
        ))}
        {jobs.length === 0 && (
          <li className="rounded border border-dashed border-line p-6 text-center text-ink-muted">
            No active assigned jobs.
          </li>
        )}
      </ul>
    </AppShell>
  );
}

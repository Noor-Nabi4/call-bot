"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  getTechnicianOpsDetail,
  setTechnicianOperationalStatus,
  TECH_OPS_STATUSES,
} from "@/lib/api/dispatch-crm";
import { hasPermission } from "@/lib/permissions";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  Field,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
} from "@/components/ui";

export default function TechnicianOpsPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth({
    permission: "technicians.read",
  });
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [nextStatus, setNextStatus] = useState("AVAILABLE");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const row = await getTechnicianOpsDetail(id);
      setData(row);
      const st = (row.status as { status?: string } | undefined)?.status;
      if (st) setNextStatus(st);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function saveStatus() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await setTechnicianOperationalStatus(id, { to_status: nextStatus });
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
        <LoadingSkeleton />
      </div>
    );
  }

  const tech = data?.technician as
    | { display_name?: string; phone?: string; is_active?: boolean }
    | undefined;
  const status = data?.status as
    | { status?: string; status_since?: string }
    | undefined;
  const skills = (data?.skills as Array<{ name?: string; key?: string }>) || [];
  const areas =
    (data?.service_areas as Array<{ name?: string; match_value?: string }>) ||
    [];
  const history =
    (data?.status_history as Array<{
      id: string;
      old_status?: string;
      new_status?: string;
      created_at?: string;
    }>) || [];

  const canUpdate =
    hasPermission(user, "dispatch.status.update") ||
    hasPermission(user, "technicians.manage");

  return (
    <AppShell user={user}>
      <PageHeader
        title={tech?.display_name || "Technician"}
        description="Operational profile — skills, areas, and status from existing domain tables."
      />
      <p className="mb-4 text-sm">
        <Link
          href="/crm/dispatch"
          className="underline-offset-2 hover:underline"
        >
          Back to dispatch
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading || !data ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <div className="flex items-center gap-2">
              <StatusPill status={status?.status || "OFFLINE"} />
              <span className="text-sm text-text-muted">
                since{" "}
                {status?.status_since
                  ? new Date(status.status_since).toLocaleString()
                  : "—"}
              </span>
            </div>
            <p>Phone: {tech?.phone || "—"}</p>
            <p>Active: {tech?.is_active ? "yes" : "no"}</p>
          </section>

          {canUpdate ? (
            <section className="flex flex-wrap items-end gap-2">
              <Field label="Set status">
                <Select
                  value={nextStatus}
                  onChange={(e) => setNextStatus(e.target.value)}
                  disabled={busy}
                >
                  {TECH_OPS_STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </Select>
              </Field>
              <Button type="button" disabled={busy} onClick={() => void saveStatus()}>
                Update status
              </Button>
            </section>
          ) : null}

          <section>
            <h2 className="mb-2 text-lg font-medium">Skills</h2>
            <ul className="text-sm">
              {skills.length === 0 ? <li>None</li> : null}
              {skills.map((s, i) => (
                <li key={s.key || i}>{s.name || s.key}</li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Service areas</h2>
            <ul className="text-sm">
              {areas.length === 0 ? <li>None (no geographic restriction)</li> : null}
              {areas.map((a, i) => (
                <li key={i}>
                  {a.name} ({a.match_value})
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">Status history</h2>
            <ul className="space-y-1 text-sm">
              {history.length === 0 ? <li>No history</li> : null}
              {history.map((h) => (
                <li key={h.id}>
                  {h.old_status || "—"} → {h.new_status}
                  {h.created_at
                    ? ` · ${new Date(h.created_at).toLocaleString()}`
                    : ""}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell, StatusPill } from "@/components/shell";
import {
  assignJob,
  createTechnician,
  formatWhen,
  listJobs,
  listTechnicians,
  transitionJob,
  type Job,
  type Technician,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";

const COLUMNS = ["new", "scheduled", "dispatched", "in_progress", "completed"] as const;

export default function BoardPage() {
  const { user, loading } = useAuth({
    roles: ["admin", "dispatcher"],
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const [techs, setTechs] = useState<Technician[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [techForm, setTechForm] = useState({
    name: "",
    email: "",
    password: "",
    phone: "",
  });

  const refresh = useCallback(async () => {
    const [j, t] = await Promise.all([listJobs(), listTechnicians()]);
    setJobs(j.jobs);
    setTechs(t.technicians);
  }, []);

  useEffect(() => {
    if (!user) return;
    refresh().catch((e) => setError(e.message));
    const id = setInterval(() => {
      refresh().catch(() => undefined);
    }, 5000);
    return () => clearInterval(id);
  }, [user, refresh]);

  if (loading || !user) {
    return <p className="p-6 text-ink-muted">Loading…</p>;
  }

  async function onAssign(jobId: string, technicianId: string) {
    setError(null);
    try {
      await assignJob(jobId, technicianId);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assign failed");
    }
  }

  async function onDispatch(jobId: string) {
    setError(null);
    try {
      await transitionJob(jobId, "dispatched");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dispatch failed");
    }
  }

  async function onCreateTech(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await createTechnician({
        name: techForm.name,
        email: techForm.email,
        password: techForm.password,
        phone: techForm.phone || undefined,
      });
      setTechForm({ name: "", email: "", password: "", phone: "" });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  return (
    <AppShell user={user}>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold">Dispatch board</h2>
          <p className="text-sm text-ink-muted">
            Assign technicians and move jobs through the field pipeline.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refresh()}
          className="rounded border border-line bg-panel px-3 py-1.5 text-sm"
        >
          Refresh
        </button>
      </div>

      {error && (
        <p className="mb-3 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-3 md:grid-cols-5">
        {COLUMNS.map((status) => {
          const columnJobs = jobs.filter((j) => j.status === status);
          return (
            <section
              key={status}
              className="min-h-48 rounded border border-line bg-panel p-2"
            >
              <header className="mb-2 flex items-center justify-between px-1">
                <StatusPill status={status} />
                <span className="font-mono text-xs text-ink-muted">
                  {columnJobs.length}
                </span>
              </header>
              <ul className="space-y-2">
                {columnJobs.map((job) => (
                  <li
                    key={job.id}
                    className="rounded border border-line bg-surface p-2 text-sm"
                  >
                    <Link
                      href={`/jobs/${job.id}`}
                      className="font-mono text-xs text-ink-muted"
                    >
                      {job.reference_code}
                    </Link>
                    <p className="font-medium">{job.service_type}</p>
                    <p className="text-ink-muted">
                      {job.customer?.name || "Customer"}
                    </p>
                    <p className="text-xs text-ink-muted">
                      {formatWhen(job.scheduled_starts_at)}
                    </p>
                    <p className="mt-1 text-xs">
                      Tech: {job.assigned_technician?.display_name || "Unassigned"}
                    </p>
                    {(status === "new" ||
                      status === "scheduled" ||
                      status === "dispatched") && (
                      <select
                        className="mt-2 w-full rounded border border-line bg-panel px-1 py-1 text-xs"
                        value={job.assigned_technician_id || ""}
                        onChange={(e) => {
                          if (e.target.value) onAssign(job.id, e.target.value);
                        }}
                      >
                        <option value="">Assign…</option>
                        {techs.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.display_name}
                          </option>
                        ))}
                      </select>
                    )}
                    {status === "scheduled" && job.assigned_technician_id && (
                      <button
                        type="button"
                        className="mt-2 w-full rounded bg-accent px-2 py-1 text-xs text-white"
                        onClick={() => onDispatch(job.id)}
                      >
                        Dispatch
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>

      <section className="mt-8 rounded border border-line bg-panel p-4">
        <h3 className="font-semibold">Add technician</h3>
        <form
          onSubmit={onCreateTech}
          className="mt-3 grid gap-2 md:grid-cols-5"
        >
          <input
            className="rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Name"
            value={techForm.name}
            onChange={(e) => setTechForm({ ...techForm, name: e.target.value })}
            required
          />
          <input
            className="rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Email"
            type="email"
            value={techForm.email}
            onChange={(e) =>
              setTechForm({ ...techForm, email: e.target.value })
            }
            required
          />
          <input
            className="rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Password"
            type="password"
            value={techForm.password}
            onChange={(e) =>
              setTechForm({ ...techForm, password: e.target.value })
            }
            required
            minLength={8}
          />
          <input
            className="rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Phone"
            value={techForm.phone}
            onChange={(e) =>
              setTechForm({ ...techForm, phone: e.target.value })
            }
          />
          <button
            type="submit"
            className="rounded bg-ink px-3 py-1.5 text-sm text-white"
          >
            Create
          </button>
        </form>
      </section>
    </AppShell>
  );
}

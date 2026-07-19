"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export default function SettingsPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const [users, setUsers] = useState<Record<string, unknown>[]>([]);
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [retention, setRetention] = useState({
    recording_retention_days: 30,
    transcript_retention_days: 90,
    audit_retention_days: 365,
  });
  const [invite, setInvite] = useState({
    name: "",
    email: "",
    password: "",
    role: "dispatcher",
  });
  const [msg, setMsg] = useState<string | null>(null);

  async function refresh() {
    const [u, a, r] = await Promise.all([
      fetch(`${API}/api/admin/users`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
      fetch(`${API}/api/admin/audit`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
      fetch(`${API}/api/admin/retention`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
    ]);
    setUsers(u.users || []);
    setAudit(a.events || []);
    if (r.settings) setRetention(r.settings);
  }

  useEffect(() => {
    if (!user) return;
    refresh().catch(() => undefined);
  }, [user]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;

  async function onInvite(e: FormEvent) {
    e.preventDefault();
    const res = await fetch(`${API}/api/admin/users`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(invite),
    });
    if (!res.ok) {
      setMsg(await res.text());
      return;
    }
    setInvite({ name: "", email: "", password: "", role: "dispatcher" });
    setMsg("User invited");
    await refresh();
  }

  async function onRetention(e: FormEvent) {
    e.preventDefault();
    await fetch(`${API}/api/admin/retention`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(retention),
    });
    setMsg("Retention saved");
  }

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Tenant settings</h2>
      <p className="text-sm text-ink-muted">
        Invite users, set retention policy, review audit log.
      </p>
      {msg && <p className="mt-2 text-sm text-accent">{msg}</p>}

      <section className="mt-6 grid gap-6 md:grid-cols-2">
        <form
          onSubmit={onInvite}
          className="space-y-2 rounded border border-line bg-panel p-4"
        >
          <h3 className="font-semibold">Invite user</h3>
          <input
            className="w-full rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Name"
            value={invite.name}
            onChange={(e) => setInvite({ ...invite, name: e.target.value })}
            required
          />
          <input
            className="w-full rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Email"
            type="email"
            value={invite.email}
            onChange={(e) => setInvite({ ...invite, email: e.target.value })}
            required
          />
          <input
            className="w-full rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Temp password"
            type="password"
            value={invite.password}
            onChange={(e) => setInvite({ ...invite, password: e.target.value })}
            required
            minLength={8}
          />
          <select
            className="w-full rounded border border-line px-2 py-1.5 text-sm"
            value={invite.role}
            onChange={(e) => setInvite({ ...invite, role: e.target.value })}
          >
            <option value="admin">admin</option>
            <option value="dispatcher">dispatcher</option>
            <option value="technician">technician</option>
          </select>
          <button
            type="submit"
            className="rounded bg-accent px-3 py-1.5 text-sm text-white"
          >
            Invite
          </button>
          <ul className="mt-3 space-y-1 text-sm">
            {users.map((u) => (
              <li key={String(u.id)}>
                {String(u.name)} · {String(u.role)} · {String(u.email)}
              </li>
            ))}
          </ul>
        </form>

        <form
          onSubmit={onRetention}
          className="space-y-2 rounded border border-line bg-panel p-4"
        >
          <h3 className="font-semibold">Retention (days)</h3>
          {(
            [
              ["recording_retention_days", "Recordings"],
              ["transcript_retention_days", "Transcripts"],
              ["audit_retention_days", "Audit"],
            ] as const
          ).map(([key, label]) => (
            <label key={key} className="block text-sm">
              {label}
              <input
                type="number"
                className="mt-1 w-full rounded border border-line px-2 py-1.5"
                value={retention[key]}
                onChange={(e) =>
                  setRetention({
                    ...retention,
                    [key]: Number(e.target.value),
                  })
                }
              />
            </label>
          ))}
          <button
            type="submit"
            className="rounded bg-ink px-3 py-1.5 text-sm text-white"
          >
            Save retention
          </button>
        </form>
      </section>

      <section className="mt-6 rounded border border-line bg-panel p-4">
        <h3 className="font-semibold">Audit log</h3>
        <ul className="mt-2 max-h-80 space-y-1 overflow-auto text-xs font-mono">
          {audit.map((e) => (
            <li key={String(e.id)}>
              {String(e.created_at)} · {String(e.actor)} · {String(e.action)}
            </li>
          ))}
        </ul>
      </section>
    </AppShell>
  );
}

"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export default function AppointmentsPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    if (!user) return;
    fetch(`${API}/api/admin/appointments`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setRows(d.appointments || []));
  }, [user]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Appointments</h2>
      <ul className="mt-4 divide-y divide-line rounded border border-line bg-panel">
        {rows.map((a) => (
          <li key={String(a.id)} className="px-3 py-2 text-sm">
            <span className="font-mono text-xs">{String(a.confirmation_code)}</span>{" "}
            {String(a.service_type)} · {String(a.status)}
            <div className="text-xs text-ink-muted">{String(a.starts_at || "")}</div>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-ink-muted">No appointments.</li>
        )}
      </ul>
    </AppShell>
  );
}

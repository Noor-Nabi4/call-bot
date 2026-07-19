"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export default function CallsPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    if (!user) return;
    fetch(`${API}/api/admin/calls`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setRows(d.calls || []));
  }, [user]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Calls</h2>
      <ul className="mt-4 divide-y divide-line rounded border border-line bg-panel">
        {rows.map((c) => (
          <li key={String(c.id)} className="px-3 py-2 text-sm font-mono">
            <span className="font-sans font-medium">{String(c.status)}</span>{" "}
            {String(c.caller_number || "—")} → {String(c.called_number || "—")}
            <div className="text-xs text-ink-muted font-sans">
              {String(c.started_at || "")}
            </div>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-ink-muted font-sans">
            No calls yet.
          </li>
        )}
      </ul>
    </AppShell>
  );
}

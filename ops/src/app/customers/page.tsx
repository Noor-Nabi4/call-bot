"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type Customer = {
  id: string;
  name: string;
  email?: string | null;
  address?: string | null;
  phones: string[];
};

export default function CustomersPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const [rows, setRows] = useState<Customer[]>([]);

  useEffect(() => {
    if (!user) return;
    fetch(`${API}/api/admin/customers`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setRows(d.customers || []));
  }, [user]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Customers</h2>
      <ul className="mt-4 divide-y divide-line rounded border border-line bg-panel">
        {rows.map((c) => (
          <li key={c.id} className="px-3 py-2 text-sm">
            <p className="font-medium">{c.name}</p>
            <p className="text-ink-muted">
              {c.phones.join(", ") || "—"}
              {c.address ? ` · ${c.address}` : ""}
            </p>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-center text-ink-muted">No customers yet.</li>
        )}
      </ul>
    </AppShell>
  );
}

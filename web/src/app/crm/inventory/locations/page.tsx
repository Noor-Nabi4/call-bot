"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { api } from "@/lib/api";
import {
  listInventoryLocations,
  type InventoryLocation,
} from "@/lib/api/inventory";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  type DataTableColumn,
} from "@/components/ui";

export default function InventoryLocationsPage() {
  const { user, loading: authLoading } = useAuth();
  const [locations, setLocations] = useState<InventoryLocation[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await listInventoryLocations();
    setLocations(data.locations);
  }, []);

  useEffect(() => {
    if (!authLoading && user) void load().catch((e) => setError(safeUserError(e)));
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/admin/crm/inventory/locations", {
        method: "POST",
        body: JSON.stringify({ name, code }),
      });
      setName("");
      setCode("");
      await load();
    } catch (err) {
      setError(safeUserError(err));
    }
  }

  const columns: DataTableColumn<InventoryLocation>[] = [
    { id: "name", header: "Name", cell: (l) => l.name },
    { id: "code", header: "Code", cell: (l) => l.code },
    { id: "type", header: "Type", cell: (l) => l.location_type },
    { id: "status", header: "Status", cell: (l) => l.status },
    {
      id: "default",
      header: "Default",
      cell: (l) => (l.is_default ? "Yes" : "—"),
    },
  ];

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={4} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Inventory locations"
        description="Warehouses, stores, vans, and other stock sites."
        actions={
          <Link href="/crm/inventory">
            <Button variant="secondary">Inventory</Button>
          </Link>
        }
      />
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <form className="mb-6 grid gap-3 md:grid-cols-3" onSubmit={onCreate}>
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </Field>
        <Field label="Code">
          <Input value={code} onChange={(e) => setCode(e.target.value)} required />
        </Field>
        <div className="flex items-end">
          <Button type="submit">Add location</Button>
        </div>
      </form>
      <DataTable columns={columns} rows={locations} />
    </AppShell>
  );
}

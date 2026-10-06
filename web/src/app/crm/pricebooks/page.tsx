"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  createPricebook,
  listPricebooks,
  type Pricebook,
} from "@/lib/api/services";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  Textarea,
  type DataTableColumn,
} from "@/components/ui";

export default function PricebooksPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<Pricebook[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    is_default: false,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listPricebooks();
      setRows(res.pricebooks);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await createPricebook({
        name: form.name,
        description: form.description || null,
        is_default: form.is_default,
      });
      setForm({ name: "", description: "", is_default: false });
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setCreating(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const columns: DataTableColumn<Pricebook>[] = [
    {
      id: "name",
      header: "Pricebook",
      cell: (row) => (
        <Link
          href={`/crm/pricebooks/${row.id}`}
          className="font-medium underline"
        >
          {row.name}
        </Link>
      ),
    },
    {
      id: "default",
      header: "Default",
      cell: (row) => (row.is_default ? "Yes" : "—"),
    },
    {
      id: "effective",
      header: "Effective",
      cell: (row) => {
        if (!row.effective_from && !row.effective_until) return "Always";
        return `${row.effective_from || "…"} → ${row.effective_until || "…"}`;
      },
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
  ];

  return (
    <AppShell user={user}>
      <PageHeader
        title="Pricebooks"
        description="Service pricing books with labor and material composition."
        actions={
          <Link href="/crm/services">
            <Button variant="secondary">Services</Button>
          </Link>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No pricebooks"
          description="Create a standard pricebook to price your services."
        />
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}

      <form onSubmit={onCreate} className="mt-8 grid max-w-xl gap-3">
        <h2 className="text-lg font-semibold">Create pricebook</h2>
        <Field label="Name">
          <Input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field label="Description">
          <Textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.is_default}
            onChange={(e) =>
              setForm({ ...form, is_default: e.target.checked })
            }
          />
          Set as default pricebook
        </label>
        <Button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create pricebook"}
        </Button>
      </form>
    </AppShell>
  );
}

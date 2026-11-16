"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  createService,
  getServiceCategoryTree,
  listServices,
  type ServiceCategory,
  type ServiceRow,
} from "@/lib/api/services";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  Field,
  FilterBar,
  Input,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  Textarea,
  type DataTableColumn,
} from "@/components/ui";

function flattenCategories(
  nodes: ServiceCategory[],
  depth = 0,
): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = [];
  for (const n of nodes) {
    out.push({ id: n.id, label: `${"— ".repeat(depth)}${n.name}` });
    if (n.children?.length) {
      out.push(...flattenCategories(n.children, depth + 1));
    }
  }
  return out;
}

export default function ServicesPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<ServiceRow[]>([]);
  const [categories, setCategories] = useState<{ id: string; label: string }[]>(
    [],
  );
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    code: "",
    description: "",
    category_id: "",
    duration_minutes: "",
    base_price: "",
    pricing_type: "FIXED",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [svc, tree] = await Promise.all([
        listServices({
          q: q || undefined,
          status: status || undefined,
          category_id: categoryId || undefined,
          limit: 100,
        }),
        getServiceCategoryTree(),
      ]);
      setRows(svc.services);
      setCategories(flattenCategories(tree.tree));
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [q, status, categoryId]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await createService({
        name: form.name,
        code: form.code || null,
        description: form.description || null,
        category_id: form.category_id || null,
        duration_minutes: form.duration_minutes
          ? Number(form.duration_minutes)
          : null,
        base_price: form.base_price || null,
        pricing_type: form.pricing_type,
      });
      setForm({
        name: "",
        code: "",
        description: "",
        category_id: "",
        duration_minutes: "",
        base_price: "",
        pricing_type: "FIXED",
      });
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
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  const columns: DataTableColumn<ServiceRow>[] = [
    {
      id: "name",
      header: "Service",
      cell: (row) => (
        <Link href={`/crm/services/${row.id}`} className="font-medium underline">
          {row.name}
        </Link>
      ),
    },
    {
      id: "code",
      header: "Code",
      cell: (row) => row.code || "—",
    },
    {
      id: "category",
      header: "Category",
      cell: (row) => row.category_name || "—",
    },
    {
      id: "duration",
      header: "Duration",
      cell: (row) =>
        row.duration_minutes != null ? `${row.duration_minutes} min` : "—",
    },
    {
      id: "price",
      header: "Base price",
      cell: (row) => row.base_price ?? "—",
    },
    {
      id: "pricing",
      header: "Type",
      cell: (row) => row.pricing_type,
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
        title="Services"
        description="Service catalog with duration and base pricing."
        actions={
          <>
            <Link href="/crm/service-categories">
              <Button variant="secondary">Categories</Button>
            </Link>
            <Link href="/crm/pricebooks">
              <Button variant="secondary">Pricebooks</Button>
            </Link>
          </>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onClear={() => setQ("")}
          placeholder="Search name, code, description"
          aria-label="Search services"
        />
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="INACTIVE">Inactive</option>
        </Select>
        <Select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </Select>
        <Button type="button" onClick={() => void load()}>
          Apply
        </Button>
      </FilterBar>

      {loading ? (
        <LoadingSkeleton rows={8} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No services yet"
          description="Create a service to start building your pricebook."
        />
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}

      <form onSubmit={onCreate} className="mt-8 grid max-w-xl gap-3">
        <h2 className="text-lg font-semibold">Create service</h2>
        <Field label="Name">
          <Input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field label="Code">
          <Input
            value={form.code}
            onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
        </Field>
        <Field label="Description">
          <Textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Field>
        <Field label="Category">
          <Select
            value={form.category_id}
            onChange={(e) => setForm({ ...form, category_id: e.target.value })}
          >
            <option value="">None</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Duration (minutes)">
          <Input
            type="number"
            min={1}
            value={form.duration_minutes}
            onChange={(e) =>
              setForm({ ...form, duration_minutes: e.target.value })
            }
          />
        </Field>
        <Field label="Base price">
          <Input
            value={form.base_price}
            onChange={(e) => setForm({ ...form, base_price: e.target.value })}
          />
        </Field>
        <Field label="Pricing type">
          <Select
            value={form.pricing_type}
            onChange={(e) => setForm({ ...form, pricing_type: e.target.value })}
          >
            <option value="FIXED">Fixed</option>
            <option value="STARTING_AT">Starting at</option>
            <option value="HOURLY">Hourly</option>
            <option value="CUSTOM_QUOTE">Custom quote</option>
          </Select>
        </Field>
        <Button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create service"}
        </Button>
      </form>
    </AppShell>
  );
}

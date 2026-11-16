"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  createPricebookItem,
  getPricebook,
  listServices,
  type Pricebook,
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
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  type DataTableColumn,
} from "@/components/ui";

type ItemRow = NonNullable<Pricebook["items"]>[number];

export default function PricebookDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [book, setBook] = useState<Pricebook | null>(null);
  const [services, setServices] = useState<ServiceRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    service_id: "",
    pricing_type: "FIXED",
    price: "",
    starting_price: "",
    hourly_rate: "",
  });

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [pb, svc] = await Promise.all([
        getPricebook(id),
        listServices({ limit: 200 }),
      ]);
      setBook(pb);
      setServices(svc.services);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await createPricebookItem(id, {
        service_id: form.service_id,
        pricing_type: form.pricing_type,
        price: form.price || null,
        starting_price: form.starting_price || null,
        hourly_rate: form.hourly_rate || null,
      });
      setForm({
        service_id: "",
        pricing_type: "FIXED",
        price: "",
        starting_price: "",
        hourly_rate: "",
      });
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setCreating(false);
    }
  }

  const columns: DataTableColumn<ItemRow>[] = [
    {
      id: "service",
      header: "Service",
      cell: (row) => row.service_name || row.service_id,
    },
    {
      id: "type",
      header: "Type",
      cell: (row) => row.pricing_type,
    },
    {
      id: "price",
      header: "Price",
      cell: (row) =>
        row.price ?? row.starting_price ?? row.hourly_rate ?? "Quote",
    },
    {
      id: "components",
      header: "Components",
      cell: (row) => String(row.components?.length ?? 0),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
  ];

  const items = book?.items ?? [];

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={book?.name || "Pricebook"}
        description="Items, labor/material composition, and overrides."
        actions={
          <Link href="/crm/pricebooks">
            <Button variant="secondary">Back</Button>
          </Link>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading || !book ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <>
          <p className="mb-4 text-sm text-text-muted">
            {book.is_default ? "Default · " : ""}
            Status: {book.status}
            {book.description ? ` · ${book.description}` : ""}
          </p>
          {items.length === 0 ? (
            <EmptyState
              title="No pricebook items"
              description="Add a service price to this pricebook."
            />
          ) : (
            <DataTable columns={columns} rows={items} />
          )}

          {(book.overrides?.length ?? 0) > 0 ? (
            <section className="mt-6">
              <h2 className="mb-2 font-semibold">Overrides</h2>
              <ul className="text-sm">
                {book.overrides?.map((o) => (
                  <li key={o.id}>
                    Service {o.service_id}: {o.override_price ?? "—"} (
                    {o.status})
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <form onSubmit={onCreate} className="mt-8 grid max-w-xl gap-3">
            <h2 className="text-lg font-semibold">Add item</h2>
            <Field label="Service">
              <Select
                required
                value={form.service_id}
                onChange={(e) =>
                  setForm({ ...form, service_id: e.target.value })
                }
              >
                <option value="">Select service</option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.code ? ` (${s.code})` : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Pricing type">
              <Select
                value={form.pricing_type}
                onChange={(e) =>
                  setForm({ ...form, pricing_type: e.target.value })
                }
              >
                <option value="FIXED">Fixed</option>
                <option value="STARTING_AT">Starting at</option>
                <option value="HOURLY">Hourly</option>
                <option value="CUSTOM_QUOTE">Custom quote</option>
              </Select>
            </Field>
            <Field label="Price">
              <Input
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
              />
            </Field>
            <Field label="Starting price">
              <Input
                value={form.starting_price}
                onChange={(e) =>
                  setForm({ ...form, starting_price: e.target.value })
                }
              />
            </Field>
            <Field label="Hourly rate">
              <Input
                value={form.hourly_rate}
                onChange={(e) =>
                  setForm({ ...form, hourly_rate: e.target.value })
                }
              />
            </Field>
            <Button type="submit" disabled={creating}>
              {creating ? "Adding…" : "Add item"}
            </Button>
          </form>
        </>
      )}
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  getInventoryItem,
  inventoryMutation,
  listInventoryLocations,
  listInventoryTransactions,
  type InventoryDetail,
  type InventoryTransaction,
} from "@/lib/api/inventory";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  type DataTableColumn,
} from "@/components/ui";

export default function InventoryDetailPage() {
  const params = useParams();
  const id = String(params.id);
  const { user, loading: authLoading } = useAuth();
  const [detail, setDetail] = useState<InventoryDetail | null>(null);
  const [txns, setTxns] = useState<InventoryTransaction[]>([]);
  const [locations, setLocations] = useState<{ id: string; label: string }[]>(
    [],
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [locationId, setLocationId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [d, t, locs] = await Promise.all([
        getInventoryItem(id),
        listInventoryTransactions(id, { limit: 50 }),
        listInventoryLocations(),
      ]);
      setDetail(d);
      setTxns(t.transactions);
      setLocations(
        locs.locations.map((l) => ({ id: l.id, label: `${l.name} (${l.code})` })),
      );
      if (d.balances[0]) {
        setLocationId((prev) => prev || d.balances[0].location_id);
      }
    } catch (e) {
      setError(safeUserError(e));
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function runAction(
    action: "purchase" | "sale" | "adjust" | "return" | "reserve" | "release",
  ) {
    if (!locationId) return;
    setBusy(true);
    setError(null);
    try {
      await inventoryMutation(
        id,
        action,
        {
          location_id: locationId,
          quantity: Number(quantity),
          reason: reason || undefined,
        },
        crypto.randomUUID(),
      );
      setReason("");
      await load();
    } catch (e) {
      setError(safeUserError(e));
    } finally {
      setBusy(false);
    }
  }

  const txnColumns: DataTableColumn<InventoryTransaction>[] = [
    {
      id: "date",
      header: "Date",
      cell: (t) => new Date(t.created_at).toLocaleString(),
    },
    { id: "type", header: "Type", cell: (t) => t.transaction_type },
    { id: "qty", header: "Qty", cell: (t) => String(t.quantity) },
    {
      id: "stock",
      header: "Stock",
      cell: (t) => `${t.stock_before} → ${t.stock_after}`,
    },
    {
      id: "reserved",
      header: "Reserved",
      cell: (t) => `${t.reserved_before} → ${t.reserved_after}`,
    },
    { id: "actor", header: "Actor", cell: (t) => t.created_by || "—" },
  ];

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
        title={detail?.product_name ?? "Inventory"}
        description={detail ? `${detail.sku}${detail.variant_name ? ` · ${detail.variant_name}` : ""}` : undefined}
        actions={
          <Link href="/crm/inventory">
            <Button variant="secondary">Back</Button>
          </Link>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {!detail ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <>
          <div className="mb-6 grid gap-3 md:grid-cols-3">
            {detail.balances.map((b) => (
              <div key={b.id} className="rounded-lg border p-4 text-sm">
                <div className="font-medium">{b.location_name}</div>
                <div>Stock: {b.stock_quantity}</div>
                <div>Reserved: {b.reserved_quantity}</div>
                <div>Available: {b.available_quantity}</div>
                <div>Minimum: {b.minimum_stock}</div>
                <div>Status: {b.status}</div>
              </div>
            ))}
          </div>
          <form
            className="mb-8 grid gap-3 md:grid-cols-4"
            onSubmit={(e: FormEvent) => e.preventDefault()}
          >
            <Field label="Location">
              <Select
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
                aria-label="Location for stock action"
              >
                {locations.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Quantity">
              <Input
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                inputMode="numeric"
                aria-label="Quantity"
              />
            </Field>
            <Field label="Reason (required for adjustment)">
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                aria-label="Reason"
              />
            </Field>
            <div className="flex flex-wrap items-end gap-2">
              {(
                [
                  "purchase",
                  "sale",
                  "adjust",
                  "return",
                  "reserve",
                  "release",
                ] as const
              ).map((action) => (
                <Button
                  key={action}
                  type="button"
                  disabled={busy}
                  onClick={() => void runAction(action)}
                >
                  {action}
                </Button>
              ))}
            </div>
          </form>
          <h2 className="mb-2 text-lg font-semibold">Transaction history</h2>
          <DataTable columns={txnColumns} rows={txns} />
        </>
      )}
    </AppShell>
  );
}

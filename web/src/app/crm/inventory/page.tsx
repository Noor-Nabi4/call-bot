"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  listInventory,
  listInventoryLocations,
  type InventoryBalanceRow,
} from "@/lib/api/inventory";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  type DataTableColumn,
} from "@/components/ui";

function filterFromSearchParams(params: URLSearchParams): string {
  if (params.get("out_of_stock") === "true") return "out";
  if (params.get("low_stock") === "true") return "low";
  const status = (params.get("status") || "").toUpperCase();
  if (status === "IN_STOCK") return "in";
  if (status === "LOW_STOCK") return "low";
  if (status === "OUT_OF_STOCK") return "out";
  return "";
}

function InventoryPageInner() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<InventoryBalanceRow[]>([]);
  const [locations, setLocations] = useState<{ id: string; label: string }[]>(
    [],
  );
  const [q, setQ] = useState(() => searchParams.get("q") || "");
  const [locationId, setLocationId] = useState(
    () => searchParams.get("location_id") || "",
  );
  const [filter, setFilter] = useState(() =>
    filterFromSearchParams(searchParams),
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setFilter(filterFromSearchParams(searchParams));
    setQ(searchParams.get("q") || "");
    setLocationId(searchParams.get("location_id") || "");
  }, [searchParams]);

  const syncUrl = useCallback(
    (next: { q?: string; locationId?: string; filter?: string }) => {
      const params = new URLSearchParams();
      const nextQ = next.q ?? q;
      const nextLoc = next.locationId ?? locationId;
      const nextFilter = next.filter ?? filter;
      if (nextQ) params.set("q", nextQ);
      if (nextLoc) params.set("location_id", nextLoc);
      if (nextFilter === "low") params.set("low_stock", "true");
      if (nextFilter === "out") params.set("out_of_stock", "true");
      if (nextFilter === "in") params.set("status", "IN_STOCK");
      const qs = params.toString();
      router.replace(qs ? `/crm/inventory?${qs}` : "/crm/inventory");
    },
    [q, locationId, filter, router],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [inv, locs] = await Promise.all([
        listInventory({
          q: q || undefined,
          location_id: locationId || undefined,
          low_stock: filter === "low",
          out_of_stock: filter === "out",
          status: filter === "in" ? "IN_STOCK" : undefined,
          limit: 100,
        }),
        listInventoryLocations(),
      ]);
      setRows(inv.inventory);
      setLocations(
        locs.locations.map((l) => ({
          id: l.id,
          label: `${l.name} (${l.code})`,
        })),
      );
    } catch (e) {
      setError(safeUserError(e));
    } finally {
      setLoading(false);
    }
  }, [q, locationId, filter]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const columns: DataTableColumn<InventoryBalanceRow>[] = [
    { id: "product", header: "Product", cell: (r) => r.product_name },
    {
      id: "variant",
      header: "Variant",
      cell: (r) => r.variant_name || "—",
    },
    { id: "sku", header: "SKU", cell: (r) => r.sku },
    { id: "location", header: "Location", cell: (r) => r.location_name },
    { id: "stock", header: "Stock", cell: (r) => String(r.stock_quantity) },
    {
      id: "reserved",
      header: "Reserved",
      cell: (r) => String(r.reserved_quantity),
    },
    {
      id: "available",
      header: "Available",
      cell: (r) => String(r.available_quantity),
    },
    {
      id: "minimum",
      header: "Minimum",
      cell: (r) => String(r.minimum_stock),
    },
    {
      id: "status",
      header: "Status",
      cell: (r) => <StatusPill status={r.status.toLowerCase()} />,
    },
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
        title="Inventory"
        description="Stock levels by SKU and location."
        actions={
          <Link href="/crm/inventory/locations">
            <Button variant="secondary">Locations</Button>
          </Link>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onClear={() => {
            setQ("");
            syncUrl({ q: "" });
          }}
          placeholder="Search SKU, product, location…"
          aria-label="Search inventory"
        />
        <Select
          value={locationId}
          onChange={(e) => {
            const value = e.target.value;
            setLocationId(value);
            syncUrl({ locationId: value });
          }}
          aria-label="Filter by location"
        >
          <option value="">All locations</option>
          {locations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.label}
            </option>
          ))}
        </Select>
        <Select
          value={filter}
          onChange={(e) => {
            const value = e.target.value;
            setFilter(value);
            syncUrl({ filter: value });
          }}
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="low">Low stock</option>
          <option value="out">Out of stock</option>
          <option value="in">In stock</option>
        </Select>
        <Button
          onClick={() => {
            syncUrl({});
            void load();
          }}
        >
          Apply
        </Button>
      </FilterBar>
      {loading ? (
        <LoadingSkeleton rows={8} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No inventory yet"
          description="Create products and variants, then receive stock at a location."
        />
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          onRowClick={(r) =>
            router.push(`/crm/inventory/${r.inventory_item_id}`)
          }
        />
      )}
    </AppShell>
  );
}

export default function InventoryPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <InventoryPageInner />
    </Suspense>
  );
}

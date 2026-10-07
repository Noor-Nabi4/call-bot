"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  listEquipment,
  type EquipmentRow,
} from "@/lib/api/equipment";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
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

function warrantyLabel(row: EquipmentRow): string {
  switch (row.warranty_status) {
    case "ACTIVE":
      return "Active";
    case "EXPIRED":
      return "Expired";
    case "NOT_ACTIVE":
      return "Not yet active";
    default:
      return "Unknown";
  }
}

export default function EquipmentListPage() {
  const { user, loading: authLoading } = useAuth();
  const [rows, setRows] = useState<EquipmentRow[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listEquipment({
        q: q.trim() || undefined,
        status: status || undefined,
        limit: 50,
      });
      setRows(res.equipment);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [q, status]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const columns: DataTableColumn<EquipmentRow>[] = [
    {
      id: "asset",
      header: "Equipment",
      cell: (row) => (
        <Link
          href={`/crm/equipment/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.manufacturer} {row.model}
        </Link>
      ),
    },
    {
      id: "serial",
      header: "Serial",
      cell: (row) => row.serial_number || "—",
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
    },
    {
      id: "warranty",
      header: "Warranty",
      cell: (row) => (
        <span className="text-sm">
          {warrantyLabel(row)}
          {row.warranty_end_date
            ? ` · ends ${new Date(row.warranty_end_date).toLocaleDateString()}`
            : null}
        </span>
      ),
    },
  ];

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Equipment"
        description="Installed assets, warranty, and service history."
        actions={
          <Link
            href="/crm/equipment/new"
            className="text-sm font-medium underline-offset-2 hover:underline"
          >
            Add equipment
          </Link>
        }
      />
      {error ? <ErrorState message={error} /> : null}
      <div className="mb-4 flex flex-wrap gap-3">
        <Field label="Search">
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Manufacturer, model, serial"
            aria-label="Search equipment"
          />
        </Field>
        <Field label="Status">
          <Select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            aria-label="Filter by status"
          >
            <option value="">All</option>
            <option value="ACTIVE">Active</option>
            <option value="INACTIVE">Inactive</option>
            <option value="RETIRED">Retired</option>
          </Select>
        </Field>
      </div>
      {loading ? (
        <LoadingSkeleton />
      ) : rows.length === 0 ? (
        <EmptyState title="No equipment yet" />
      ) : (
        <DataTable columns={columns} rows={rows} />
      )}
    </AppShell>
  );
}

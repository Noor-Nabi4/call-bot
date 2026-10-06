"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  APPOINTMENT_STATUSES,
  appointmentStatusLabel,
  listCrmAppointments,
  type AppointmentRow,
} from "@/lib/api/appointments-crm";
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

export default function CrmAppointmentsPage() {
  const { user, loading: authLoading } = useAuth({
    permission: "appointments.read",
  });
  const [rows, setRows] = useState<AppointmentRow[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await listCrmAppointments({
        q: q || undefined,
        status: status || undefined,
        limit: 50,
        cursor: cursor || undefined,
      });
      setRows(list.appointments);
      setNextCursor(list.next_cursor ?? null);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [q, status, cursor]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const columns: DataTableColumn<AppointmentRow>[] = [
    {
      id: "appointment_number",
      header: "Appointment",
      cell: (row) => (
        <Link
          href={`/crm/appointments/${row.id}`}
          className="font-medium underline-offset-2 hover:underline"
        >
          {row.appointment_number}
        </Link>
      ),
    },
    {
      id: "customer",
      header: "Customer",
      cell: (row) => row.customer?.display_name || row.customer?.name || "—",
    },
    {
      id: "service",
      header: "Service",
      cell: (row) => row.service?.name || row.service_type || "—",
    },
    {
      id: "technician",
      header: "Technician",
      cell: (row) => row.assigned_technician?.display_name || "—",
    },
    {
      id: "starts_at",
      header: "Starts",
      cell: (row) =>
        row.starts_at ? new Date(row.starts_at).toLocaleString() : "—",
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
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
        title="Appointments"
        description="Scheduled customer engagements linked to jobs and technicians."
        actions={
          <Link
            href="/crm/availability"
            className="inline-flex h-9 items-center rounded-md border px-3 text-sm"
          >
            Find availability
          </Link>
        }
      />
      <FilterBar>
        <SearchInput
          value={q}
          onChange={(e) => {
            setCursor(null);
            setQ(e.target.value);
          }}
          placeholder="Search number, customer, service…"
        />
        <Select
          value={status}
          onChange={(e) => {
            setCursor(null);
            setStatus(e.target.value);
          }}
        >
          <option value="">All statuses</option>
          {APPOINTMENT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {appointmentStatusLabel(s)}
            </option>
          ))}
        </Select>
      </FilterBar>
      {loading ? <LoadingSkeleton /> : null}
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {!loading && !error && rows.length === 0 ? (
        <EmptyState
          title="No appointments"
          description="Book an appointment from availability or the voice scheduling tools."
        />
      ) : null}
      {!loading && !error && rows.length > 0 ? (
        <>
          <DataTable columns={columns} rows={rows} />
          <div className="mt-4 flex gap-2">
            <Button
              type="button"
              variant="secondary"
              disabled={!cursor}
              onClick={() => setCursor(null)}
            >
              First page
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={!nextCursor}
              onClick={() => nextCursor && setCursor(nextCursor)}
            >
              Next page
            </Button>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

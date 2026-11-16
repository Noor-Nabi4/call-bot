"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { listTechnicians } from "@/lib/api/technicians";
import type { Technician } from "@/types";
import {
  APPOINTMENT_CANCELLABLE,
  APPOINTMENT_FORWARD,
  assignCrmAppointment,
  appointmentStatusLabel,
  cancelCrmAppointment,
  getCrmAppointment,
  getCrmAppointmentHistory,
  rescheduleCrmAppointment,
  transitionCrmAppointment,
  type AppointmentHistoryRow,
  type AppointmentRow,
} from "@/lib/api/appointments-crm";
import { isBookingConflict } from "@/lib/api/client";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  Textarea,
} from "@/components/ui";

export default function CrmAppointmentDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth({
    permission: "appointments.read",
  });
  const [appt, setAppt] = useState<AppointmentRow | null>(null);
  const [history, setHistory] = useState<AppointmentHistoryRow[]>([]);
  const [technicians, setTechnicians] = useState<Technician[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [techId, setTechId] = useState("");
  const [rescheduleAt, setRescheduleAt] = useState("");
  const [info, setInfo] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [row, hist, techRes] = await Promise.all([
        getCrmAppointment(id),
        getCrmAppointmentHistory(id),
        listTechnicians().catch(() => ({ technicians: [] as Technician[] })),
      ]);
      setAppt(row);
      setHistory(hist.history);
      setTechnicians(techRes.technicians);
      setTechId(row.assigned_technician_id || "");
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function runAction(fn: () => Promise<AppointmentRow>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const updated = await fn();
      setAppt(updated);
      const hist = await getCrmAppointmentHistory(id);
      setHistory(hist.history);
    } catch (err) {
      if (isBookingConflict(err)) {
        setInfo(
          "Schedule conflict — another booking holds that window. Reload and try a different time.",
        );
      } else {
        setError(safeUserError(err));
      }
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  const forwards = appt ? APPOINTMENT_FORWARD[appt.status] || [] : [];

  return (
    <AppShell user={user}>
      <PageHeader
        title={appt?.appointment_number || "Appointment"}
        description="Lifecycle transitions go through the transition API — status is not freely editable."
      />
      <p className="mb-4 text-sm">
        <Link
          href="/crm/appointments"
          className="underline-offset-2 hover:underline"
        >
          Back to appointments
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {info ? (
        <p className="mb-4 text-sm" role="status">
          {info}
        </p>
      ) : null}
      {loading || !appt ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={appt.status} />
              {appt.is_emergency ? (
                <span className="text-sm">Emergency</span>
              ) : null}
            </div>
            <p>
              <strong>Customer:</strong>{" "}
              {appt.customer?.display_name || appt.customer?.name || "—"}
            </p>
            <p>
              <strong>Location:</strong>{" "}
              {appt.location
                ? [appt.location.address_line_1, appt.location.city]
                    .filter(Boolean)
                    .join(", ")
                : "—"}
            </p>
            <p>
              <strong>Technician:</strong>{" "}
              {appt.assigned_technician?.display_name || "Unassigned"}
            </p>
            <p>
              <strong>Window:</strong>{" "}
              {appt.starts_at
                ? new Date(appt.starts_at).toLocaleString()
                : "—"}
              {" → "}
              {appt.ends_at ? new Date(appt.ends_at).toLocaleString() : "—"}
            </p>
            <p>
              <strong>Duration:</strong> {appt.duration_minutes ?? "—"} min
              {appt.timezone ? ` · ${appt.timezone}` : ""}
            </p>
            {appt.job_id ? (
              <p>
                <strong>Job:</strong>{" "}
                <Link
                  href={`/crm/jobs/${appt.job_id}`}
                  className="underline-offset-2 hover:underline"
                >
                  Open job
                </Link>
              </p>
            ) : null}
            {appt.notes ? (
              <p className="whitespace-pre-wrap">{appt.notes}</p>
            ) : null}
          </section>

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Actions</h2>
            <div className="flex flex-wrap gap-2">
              {forwards.map((to) => (
                <Button
                  key={to}
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      transitionCrmAppointment(id, { to_status: to }),
                    )
                  }
                >
                  Mark {appointmentStatusLabel(to)}
                </Button>
              ))}
              {APPOINTMENT_CANCELLABLE.has(appt.status) ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      cancelCrmAppointment(id, {
                        reason: cancelReason || undefined,
                      }),
                    )
                  }
                >
                  Cancel
                </Button>
              ) : null}
            </div>
            {APPOINTMENT_CANCELLABLE.has(appt.status) ? (
              <Field label="Cancel reason">
                <Textarea
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  rows={2}
                />
              </Field>
            ) : null}

            <Field label="Assign technician">
              <div className="flex gap-2">
                <Select
                  value={techId}
                  onChange={(e) => setTechId(e.target.value)}
                  disabled={busy}
                >
                  <option value="">Unassigned</option>
                  {technicians.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.display_name}
                    </option>
                  ))}
                </Select>
                <Button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      assignCrmAppointment(id, {
                        technician_id: techId || null,
                      }),
                    )
                  }
                >
                  Save
                </Button>
              </div>
            </Field>

            {APPOINTMENT_CANCELLABLE.has(appt.status) ? (
              <Field label="Reschedule (local datetime)">
                <div className="flex flex-wrap gap-2">
                  <Input
                    type="datetime-local"
                    value={rescheduleAt}
                    onChange={(e) => setRescheduleAt(e.target.value)}
                    disabled={busy}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy || !rescheduleAt}
                    onClick={() => {
                      if (!rescheduleAt) return;
                      const iso = new Date(rescheduleAt).toISOString();
                      void runAction(() =>
                        rescheduleCrmAppointment(id, { starts_at: iso }),
                      );
                    }}
                  >
                    Reschedule
                  </Button>
                </div>
              </Field>
            ) : null}
          </section>

          <section>
            <h2 className="mb-2 text-lg font-medium">History</h2>
            <ul className="space-y-2 text-sm">
              {history.map((h) => (
                <li key={h.id}>
                  {h.from_status || "—"} → {h.to_status}
                  {h.reason ? ` (${h.reason})` : ""}
                  {h.created_at
                    ? ` · ${new Date(h.created_at).toLocaleString()}`
                    : ""}
                </li>
              ))}
              {history.length === 0 ? <li>No history yet.</li> : null}
            </ul>
          </section>
        </div>
      )}
    </AppShell>
  );
}

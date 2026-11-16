"use client";

import Link from "next/link";
import {
  CalendarDays,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  GripVertical,
  UserRoundCog,
} from "lucide-react";
import {
  DragEvent,
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { AppShell } from "@/components/shell";
import {
  appointmentStatusLabel,
  assignCrmAppointment,
  listCrmAppointments,
  rescheduleCrmAppointment,
  type AppointmentRow,
} from "@/lib/api/appointments-crm";
import { listTechnicians } from "@/lib/api/technicians";
import { useAuth } from "@/lib/use-auth";
import { hasPermission } from "@/lib/permissions";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  useToast,
} from "@/components/ui";
import type { Technician } from "@/types";

type ViewMode = "day" | "week" | "technician";

const HOURS = Array.from({ length: 13 }, (_, i) => i + 7); // 7:00–19:00

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function startOfWeek(d: Date): Date {
  const x = startOfDay(d);
  const day = x.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday start
  return addDays(x, diff);
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function formatDayLabel(d: Date): string {
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function slotIso(day: Date, hour: number): string {
  const d = new Date(day);
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

function ApptCard({
  appt,
  canDrag,
  onDragStart,
}: {
  appt: AppointmentRow;
  canDrag: boolean;
  onDragStart: (id: string) => void;
}) {
  const customer =
    appt.customer?.display_name || appt.customer?.name || "Customer";
  const service = appt.service?.name || appt.service_type;
  const tech = appt.assigned_technician?.display_name || "Unassigned";

  return (
    <div
      draggable={canDrag}
      onDragStart={() => canDrag && onDragStart(appt.id)}
      className={[
        "rounded-lg border border-border bg-surface px-2.5 py-2 text-left shadow-sm",
        canDrag ? "cursor-grab active:cursor-grabbing" : "",
      ].join(" ")}
    >
      <div className="flex items-start gap-1.5">
        {canDrag ? (
          <GripVertical
            className="mt-0.5 size-3.5 shrink-0 text-text-muted"
            strokeWidth={1.8}
            aria-hidden
          />
        ) : null}
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] text-text-muted">
            {formatTime(appt.starts_at)}
          </p>
          <Link
            href={`/crm/appointments/${appt.id}`}
            className="block truncate text-sm font-medium text-text-primary underline-offset-2 hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {service}
          </Link>
          <p className="truncate text-xs text-text-secondary">{customer}</p>
          <p className="truncate text-[11px] text-text-muted">{tech}</p>
          <div className="mt-1">
            <StatusPill status={appointmentStatusLabel(appt.status)} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SchedulingPage() {
  const { user, loading: authLoading } = useAuth({
    permission: "appointments.read",
  });
  const toast = useToast();
  const canWrite = Boolean(user && hasPermission(user, "appointments.update"));

  const [view, setView] = useState<ViewMode>("week");
  const [anchor, setAnchor] = useState(() => startOfDay(new Date()));
  const [rows, setRows] = useState<AppointmentRow[]>([]);
  const [techs, setTechs] = useState<Technician[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<{
    appointment: AppointmentRow;
    newStartsAt: string;
    technicianId?: string | null;
  } | null>(null);

  const range = useMemo(() => {
    if (view === "day") {
      return { from: anchor, to: addDays(anchor, 1) };
    }
    if (view === "technician") {
      return { from: anchor, to: addDays(anchor, 1) };
    }
    const weekStart = startOfWeek(anchor);
    return { from: weekStart, to: addDays(weekStart, 7) };
  }, [anchor, view]);

  const days = useMemo(() => {
    if (view === "week") {
      return Array.from({ length: 7 }, (_, i) => addDays(range.from, i));
    }
    return [anchor];
  }, [view, range.from, anchor]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, techList] = await Promise.all([
        listCrmAppointments({
          starts_from: range.from.toISOString(),
          starts_to: new Date(range.to.getTime() - 1).toISOString(),
          limit: 200,
        }),
        listTechnicians().catch(() => ({ technicians: [] as Technician[] })),
      ]);
      setRows(list.appointments);
      setTechs(techList.technicians || []);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [range.from, range.to]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const byDay = useMemo(() => {
    const map = new Map<string, AppointmentRow[]>();
    for (const day of days) {
      map.set(day.toDateString(), []);
    }
    for (const appt of rows) {
      if (!appt.starts_at) continue;
      const key = startOfDay(new Date(appt.starts_at)).toDateString();
      const bucket = map.get(key);
      if (bucket) bucket.push(appt);
    }
    for (const list of map.values()) {
      list.sort((a, b) =>
        String(a.starts_at).localeCompare(String(b.starts_at)),
      );
    }
    return map;
  }, [rows, days]);

  function onDropSlot(
    day: Date,
    hour: number,
    technicianId?: string | null,
  ) {
    if (!draggingId || !canWrite) return;
    const appointment = rows.find((r) => r.id === draggingId);
    if (!appointment) return;
    const newStartsAt = slotIso(day, hour);
    setConfirm({
      appointment,
      newStartsAt,
      technicianId:
        technicianId === undefined
          ? undefined
          : technicianId,
    });
    setDraggingId(null);
  }

  async function applyReschedule() {
    if (!confirm) return;
    setBusy(true);
    try {
      const updated = await rescheduleCrmAppointment(confirm.appointment.id, {
        starts_at: confirm.newStartsAt,
      });
      if (
        confirm.technicianId !== undefined &&
        confirm.technicianId !==
          (confirm.appointment.assigned_technician_id || null)
      ) {
        await assignCrmAppointment(confirm.appointment.id, {
          technician_id: confirm.technicianId,
        });
      }
      setRows((prev) =>
        prev.map((r) =>
          r.id === updated.id
            ? {
                ...r,
                ...updated,
                assigned_technician_id:
                  confirm.technicianId !== undefined
                    ? confirm.technicianId
                    : r.assigned_technician_id,
              }
            : r,
        ),
      );
      toast.push("Appointment rescheduled", "success");
      setConfirm(null);
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Unable to reschedule appointment"), "error");
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Scheduling"
        description="Day, week, and technician calendar from live appointments."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-lg border border-border p-0.5">
              {(
                [
                  { id: "day", label: "Day", icon: CalendarRange },
                  { id: "week", label: "Week", icon: CalendarDays },
                  { id: "technician", label: "Technician", icon: UserRoundCog },
                ] as const
              ).map((opt) => {
                const Icon = opt.icon;
                const active = view === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setView(opt.id)}
                    className={[
                      "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition",
                      active
                        ? "bg-brand/10 text-brand"
                        : "text-text-secondary hover:bg-surface-muted",
                    ].join(" ")}
                    aria-pressed={active}
                  >
                    <Icon className="size-3.5" strokeWidth={1.8} aria-hidden />
                    {opt.label}
                  </button>
                );
              })}
            </div>
            <div className="inline-flex items-center gap-1">
              <Button
                variant="secondary"
                size="sm"
                aria-label="Previous"
                onClick={() =>
                  setAnchor((d) =>
                    addDays(d, view === "week" ? -7 : -1),
                  )
                }
              >
                <ChevronLeft className="size-4" aria-hidden />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setAnchor(startOfDay(new Date()))}
              >
                Today
              </Button>
              <Button
                variant="secondary"
                size="sm"
                aria-label="Next"
                onClick={() =>
                  setAnchor((d) => addDays(d, view === "week" ? 7 : 1))
                }
              >
                <ChevronRight className="size-4" aria-hidden />
              </Button>
            </div>
            <Link href="/crm/appointments">
              <Button variant="secondary" size="sm">
                List view
              </Button>
            </Link>
          </div>
        }
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={load} />
      ) : null}

      {loading ? (
        <LoadingSkeleton rows={10} />
      ) : rows.length === 0 && view !== "technician" ? (
        <EmptyState
          title="No appointments found"
          description="There are no appointments for this date range."
        />
      ) : view === "technician" ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <div
            className="grid min-w-[720px]"
            style={{
              gridTemplateColumns: `72px repeat(${Math.max(techs.length, 1)}, minmax(160px, 1fr))`,
            }}
          >
            <div className="border-b border-border bg-surface-muted/50 px-2 py-2 text-xs text-text-muted" />
            {(techs.length
              ? techs
              : [
                  {
                    id: "none",
                    display_name: "Unassigned",
                    is_active: true,
                  } satisfies Technician,
                ]
            ).map((tech) => (
                <div
                  key={tech.id}
                  className="border-b border-l border-border bg-surface-muted/50 px-2 py-2"
                >
                  <p className="truncate text-sm font-medium text-text-primary">
                    {tech.display_name || "Technician"}
                  </p>
                  <p className="text-[11px] text-text-muted">
                    {
                      rows.filter(
                        (r) =>
                          (r.assigned_technician_id || "none") === tech.id ||
                          (tech.id === "none" && !r.assigned_technician_id),
                      ).length
                    }{" "}
                    jobs
                  </p>
                </div>
              ))}
            {HOURS.map((hour) => (
              <Fragment key={`tech-row-${hour}`}>
                <div className="border-b border-border px-2 py-6 text-xs tabular-nums text-text-muted">
                  {`${hour}:00`}
                </div>
                {(techs.length
                  ? techs
                  : [
                      {
                        id: "none",
                        display_name: "Unassigned",
                        is_active: true,
                      } satisfies Technician,
                    ]
                ).map((tech) => {
                  const slotAppts = rows.filter((r) => {
                    if (!r.starts_at) return false;
                    const starts = new Date(r.starts_at);
                    if (!sameDay(starts, anchor)) return false;
                    if (starts.getHours() !== hour) return false;
                    const tid = r.assigned_technician_id || "none";
                    return tid === tech.id;
                  });
                  return (
                    <div
                      key={`${tech.id}-${hour}`}
                      className="min-h-[72px] space-y-1.5 border-b border-l border-border bg-surface p-1.5"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e: DragEvent) => {
                        e.preventDefault();
                        onDropSlot(
                          anchor,
                          hour,
                          tech.id === "none" ? null : tech.id,
                        );
                      }}
                    >
                      {slotAppts.map((appt) => (
                        <ApptCard
                          key={appt.id}
                          appt={appt}
                          canDrag={canWrite}
                          onDragStart={setDraggingId}
                        />
                      ))}
                    </div>
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <div
            className="grid min-w-[640px]"
            style={{
              gridTemplateColumns: `72px repeat(${days.length}, minmax(140px, 1fr))`,
            }}
          >
            <div className="border-b border-border bg-surface-muted/50 px-2 py-2" />
            {days.map((day) => (
              <div
                key={day.toISOString()}
                className={[
                  "border-b border-l border-border bg-surface-muted/50 px-2 py-2 text-center",
                  sameDay(day, new Date()) ? "text-brand" : "",
                ].join(" ")}
              >
                <p className="text-xs font-medium">{formatDayLabel(day)}</p>
                <p className="text-[11px] text-text-muted">
                  {(byDay.get(day.toDateString()) || []).length} appts
                </p>
              </div>
            ))}
            {HOURS.map((hour) => (
              <Fragment key={`day-row-${hour}`}>
                <div className="border-b border-border px-2 py-6 text-xs tabular-nums text-text-muted">
                  {`${hour}:00`}
                </div>
                {days.map((day) => {
                  const slotAppts = (byDay.get(day.toDateString()) || []).filter(
                    (r) =>
                      r.starts_at &&
                      new Date(r.starts_at).getHours() === hour,
                  );
                  return (
                    <div
                      key={`${day.toISOString()}-${hour}`}
                      className="min-h-[72px] space-y-1.5 border-b border-l border-border bg-surface p-1.5"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e: DragEvent) => {
                        e.preventDefault();
                        onDropSlot(day, hour);
                      }}
                    >
                      {slotAppts.map((appt) => (
                        <ApptCard
                          key={appt.id}
                          appt={appt}
                          canDrag={canWrite}
                          onDragStart={setDraggingId}
                        />
                      ))}
                    </div>
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      )}

      {confirm ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reschedule-title"
        >
          <div className="w-full max-w-md rounded-xl border border-border bg-surface p-4 shadow-lg">
            <h2
              id="reschedule-title"
              className="font-heading text-lg font-semibold text-text-primary"
            >
              Reschedule appointment?
            </h2>
            <p className="mt-2 text-sm text-text-secondary">
              {confirm.appointment.service?.name ||
                confirm.appointment.service_type}
            </p>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-text-muted">Current</dt>
                <dd className="font-medium text-text-primary">
                  {formatTime(confirm.appointment.starts_at)} ·{" "}
                  {confirm.appointment.starts_at
                    ? formatDayLabel(new Date(confirm.appointment.starts_at))
                    : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-text-muted">New</dt>
                <dd className="font-medium text-text-primary">
                  {formatTime(confirm.newStartsAt)} ·{" "}
                  {formatDayLabel(new Date(confirm.newStartsAt))}
                </dd>
              </div>
            </dl>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={busy}
                onClick={() => setConfirm(null)}
              >
                Cancel
              </Button>
              <Button size="sm" disabled={busy} onClick={() => void applyReschedule()}>
                {busy ? "Saving…" : "Confirm"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

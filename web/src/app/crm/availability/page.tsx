"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  createCrmAppointment,
  queryAvailability,
  type AvailabilitySlot,
} from "@/lib/api/appointments-crm";
import { isBookingConflict } from "@/lib/api/client";
import { hasPermission } from "@/lib/permissions";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function plusDaysIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function CrmAvailabilityPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth({
    permission: "appointments.availability.read",
  });
  const [fromDate, setFromDate] = useState(todayIso);
  const [toDate, setToDate] = useState(plusDaysIso(7));
  const [duration, setDuration] = useState("60");
  const [customerId, setCustomerId] = useState("");
  const [emergency, setEmergency] = useState(false);
  const [slots, setSlots] = useState<AvailabilitySlot[]>([]);
  const [timezone, setTimezone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [bookingKey, setBookingKey] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  const search = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await queryAvailability({
        from_date: fromDate,
        to_date: toDate,
        duration_minutes: Number(duration) || 60,
        is_emergency: emergency,
        limit: 100,
      });
      setSlots(result.slots || []);
      setTimezone(result.timezone || "");
      setSearched(true);
    } catch (err) {
      setError(safeUserError(err));
      setSlots([]);
    } finally {
      setBusy(false);
    }
  }, [fromDate, toDate, duration, emergency]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setInfo(null);
    await search();
  }

  async function bookSlot(slot: AvailabilitySlot) {
    if (busy || bookingKey) return;
    const cid = customerId.trim();
    if (!cid) {
      setError("Enter a customer ID before booking a slot.");
      return;
    }
    const key = `${slot.starts_at}-${slot.technician_id || "any"}`;
    setBookingKey(key);
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const appt = await createCrmAppointment({
        customer_id: cid,
        starts_at: slot.starts_at,
        ends_at: slot.ends_at,
        duration_minutes: Number(duration) || undefined,
        technician_id: slot.technician_id || null,
        is_emergency: emergency,
      });
      router.push(`/crm/appointments/${appt.id}`);
    } catch (err) {
      if (isBookingConflict(err)) {
        setInfo(
          "That slot was just taken. Availability refreshed — pick another window.",
        );
        await search();
      } else {
        setError(safeUserError(err));
      }
    } finally {
      setBookingKey(null);
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

  return (
    <AppShell user={user}>
      <PageHeader
        title="Availability"
        description="Computed windows from business hours, technician schedules, and existing appointments. Advisory only — booking revalidates."
        actions={
          <Link
            href="/crm/appointments"
            className="underline-offset-2 hover:underline text-sm"
          >
            Appointments
          </Link>
        }
      />

      <form onSubmit={onSubmit} className="mb-6 grid max-w-xl gap-3">
        <Field label="From date">
          <Input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            required
          />
        </Field>
        <Field label="To date">
          <Input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            required
          />
        </Field>
        <Field label="Duration (minutes)">
          <Input
            type="number"
            min={1}
            max={1440}
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          />
        </Field>
        <Field label="Customer ID (required to book)">
          <Input
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="UUID of the customer"
            autoComplete="off"
          />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={emergency}
            onChange={(e) => setEmergency(e.target.checked)}
          />
          Emergency hours
        </label>
        <Button type="submit" disabled={busy}>
          {busy && !bookingKey ? "Searching…" : "Search availability"}
        </Button>
      </form>

      {error ? <ErrorState message={error} /> : null}
      {info ? (
        <p className="mb-4 text-sm" role="status">
          {info}
        </p>
      ) : null}

      {searched && !error && slots.length === 0 ? (
        <EmptyState
          title="No open windows"
          description="Try a wider date range, shorter duration, or emergency hours."
        />
      ) : null}

      {slots.length > 0 ? (
        <div className="space-y-2">
          {timezone ? (
            <p className="text-sm text-text-muted">
              Business timezone: {timezone} · times shown in your locale
            </p>
          ) : null}
          <ul className="divide-y rounded-md border border-border">
            {slots.map((s) => {
              const key = `${s.starts_at}-${s.technician_id || "any"}`;
              return (
                <li
                  key={key}
                  className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2 text-sm"
                >
                  <span>
                    {s.local_start
                      ? new Date(s.local_start).toLocaleString()
                      : new Date(s.starts_at).toLocaleString()}
                    {" – "}
                    {s.local_end
                      ? new Date(s.local_end).toLocaleTimeString()
                      : new Date(s.ends_at).toLocaleTimeString()}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="text-text-muted">
                      {s.technician_name || "Any eligible technician"}
                    </span>
                    {hasPermission(user, "appointments.create") ? (
                      <Button
                        type="button"
                        variant="secondary"
                        disabled={busy || bookingKey === key}
                        onClick={() => void bookSlot(s)}
                      >
                        {bookingKey === key ? "Booking…" : "Book"}
                      </Button>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </AppShell>
  );
}

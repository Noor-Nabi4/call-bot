"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { createEquipment } from "@/lib/api/equipment";
import {
  getCrmCustomer,
  type CustomerLocation,
} from "@/lib/api/customers";
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
  Textarea,
} from "@/components/ui";

function NewEquipmentPageInner() {
  const router = useRouter();
  const params = useSearchParams();
  const customerId = params.get("customer_id") || "";
  const { user, loading: authLoading } = useAuth();
  const [locations, setLocations] = useState<CustomerLocation[]>([]);
  const [manufacturer, setManufacturer] = useState("");
  const [model, setModel] = useState("");
  const [serial, setSerial] = useState("");
  const [locationId, setLocationId] = useState("");
  const [installDate, setInstallDate] = useState("");
  const [wStart, setWStart] = useState("");
  const [wEnd, setWEnd] = useState("");
  const [provider, setProvider] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(!!customerId);

  const loadCustomer = useCallback(async () => {
    if (!customerId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const c = await getCrmCustomer(customerId);
      const locs = c.customer.locations || [];
      setLocations(locs);
      const primary = locs.find((l) => l.is_primary);
      if (primary) setLocationId(primary.id);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    if (!authLoading && user) void loadCustomer();
  }, [authLoading, user, loadCustomer]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!customerId || busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createEquipment({
        customer_id: customerId,
        manufacturer: manufacturer.trim(),
        model: model.trim(),
        location_id: locationId || undefined,
        serial_number: serial.trim() || undefined,
        installation_date: installDate || undefined,
        warranty_start_date: wStart || undefined,
        warranty_end_date: wEnd || undefined,
        warranty_provider: provider.trim() || undefined,
        notes: notes.trim() || undefined,
        status: "ACTIVE",
      });
      router.push(`/crm/equipment/${created.id}`);
    } catch (err) {
      setError(safeUserError(err));
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

  if (!customerId) {
    return (
      <AppShell user={user}>
        <PageHeader title="Add equipment" />
        <p className="text-sm text-neutral-600">
          Open this form from a customer profile (Add equipment) so the customer is
          pre-selected.
        </p>
        <Link href="/crm/equipment" className="mt-4 inline-block text-sm underline">
          Back to equipment
        </Link>
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader title="Add equipment" />
      <p className="mb-4 text-sm">
        <Link href={`/customers/${customerId}`} className="underline-offset-2 hover:underline">
          Back to customer
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading ? (
        <LoadingSkeleton />
      ) : (
        <form className="max-w-lg space-y-4" onSubmit={onSubmit}>
          <Field label="Manufacturer">
            <Input value={manufacturer} onChange={(e) => setManufacturer(e.target.value)} required />
          </Field>
          <Field label="Model">
            <Input value={model} onChange={(e) => setModel(e.target.value)} required />
          </Field>
          <Field label="Serial number">
            <Input value={serial} onChange={(e) => setSerial(e.target.value)} />
          </Field>
          <Field label="Location">
            <Select
              value={locationId}
              onChange={(e) => setLocationId(e.target.value)}
              aria-label="Installation location"
            >
              <option value="">None</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.label || loc.address_line_1}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Installation date">
            <Input type="date" value={installDate} onChange={(e) => setInstallDate(e.target.value)} />
          </Field>
          <Field label="Warranty start">
            <Input type="date" value={wStart} onChange={(e) => setWStart(e.target.value)} />
          </Field>
          <Field label="Warranty end">
            <Input type="date" value={wEnd} onChange={(e) => setWEnd(e.target.value)} />
          </Field>
          <Field label="Warranty provider">
            <Input value={provider} onChange={(e) => setProvider(e.target.value)} />
          </Field>
          <Field label="Notes">
            <Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          <Button type="submit" variant="ink" disabled={busy}>
            {busy ? "Saving…" : "Create equipment"}
          </Button>
        </form>
      )}
    </AppShell>
  );
}

export default function NewEquipmentPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton />
        </div>
      }
    >
      <NewEquipmentPageInner />
    </Suspense>
  );
}

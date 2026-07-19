"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Phone,
  Radio,
} from "lucide-react";
import { PageShell } from "@/components/shell";
import { Button, EmptyHint, ErrorBanner, Field, TextInput } from "@/components/ui";
import { cn } from "@/lib/cn";

type PhoneNumber = {
  id: string;
  e164: string;
  connection_status: string;
  verification_status: string;
  onboarding_path?: string;
  provisioning_state?: string;
};

type InventoryItem = {
  e164: string;
  friendly_name?: string | null;
  locality?: string | null;
  region?: string | null;
  monthly_price?: string | null;
  price_unit?: string | null;
  capabilities?: Record<string, boolean>;
};

const defaultPlatformUrl =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.trim() || "http://127.0.0.1:8000";

const STEPS = [
  { id: "number", label: "Number" },
  { id: "provider", label: "Provider" },
  { id: "configure", label: "Configure" },
  { id: "test", label: "Test" },
  { id: "activate", label: "Activate" },
] as const;

async function api<T>(
  base: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || data?.error || res.statusText;
    throw new Error(message);
  }
  return data as T;
}

export default function TelephonyWizardPage() {
  const [step, setStep] = useState(0);
  const [platformUrl, setPlatformUrl] = useState(defaultPlatformUrl);
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [path, setPath] = useState<"existing" | "purchase">("existing");
  const [connectNumber, setConnectNumber] = useState("");
  const [twilioTrunkSid, setTwilioTrunkSid] = useState("");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [setupSteps, setSetupSteps] = useState<unknown>(null);
  const [country, setCountry] = useState("US");
  const [areaCode, setAreaCode] = useState("");
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [selectedPurchase, setSelectedPurchase] = useState("");
  const [numbers, setNumbers] = useState<PhoneNumber[]>([]);
  const [log, setLog] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canAct = useMemo(
    () => Boolean(platformUrl && tenantId),
    [platformUrl, tenantId],
  );

  function pushLog(message: string) {
    setLog((prev) => `${new Date().toISOString()}  ${message}\n${prev}`);
  }

  async function createTenant(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const tenant = await api<{ id: string }>(platformUrl, "/tenants", {
        method: "POST",
        body: JSON.stringify({ name: tenantName, slug: tenantSlug }),
      });
      setTenantId(tenant.id);
      pushLog(`Created tenant ${tenant.id}`);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      pushLog(`Create tenant failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function refreshNumbers() {
    if (!tenantId) return;
    const data = await api<{ items: PhoneNumber[] }>(
      platformUrl,
      `/tenants/${tenantId}/phone-numbers`,
    );
    setNumbers(data.items);
  }

  async function connectExisting(e: FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api<{
        phone_number: PhoneNumber;
        twilio_setup: unknown;
      }>(platformUrl, `/tenants/${tenantId}/phone-numbers/connect`, {
        method: "POST",
        body: JSON.stringify({ phone_number: connectNumber }),
      });
      setPhoneNumberId(data.phone_number.id);
      setSetupSteps(data.twilio_setup);
      pushLog(`Connected ${data.phone_number.e164} → ${data.phone_number.id}`);
      await refreshNumbers();
      setStep(2);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      pushLog(`Connect failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirmTrunk(e: FormEvent) {
    e.preventDefault();
    if (!tenantId || !phoneNumberId) return;
    setBusy(true);
    setError(null);
    try {
      await api(
        platformUrl,
        `/tenants/${tenantId}/phone-numbers/${phoneNumberId}/confirm-trunk`,
        {
          method: "POST",
          body: JSON.stringify({ twilio_trunk_sid: twilioTrunkSid || null }),
        },
      );
      pushLog("Trunk confirmed; start verification next");
      await refreshNumbers();
      setStep(3);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      pushLog(`Confirm trunk failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function startVerification() {
    if (!tenantId || !phoneNumberId) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api<{ instructions: string }>(
        platformUrl,
        `/tenants/${tenantId}/phone-numbers/${phoneNumberId}/verification/start`,
        { method: "POST" },
      );
      pushLog(data.instructions);
      await refreshNumbers();
      setStep(4);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      pushLog(`Verification start failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function searchInventory(e: FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setBusy(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        country,
        number_type: "local",
        limit: "10",
      });
      if (areaCode) qs.set("area_code", areaCode);
      const data = await api<{ items: InventoryItem[] }>(
        platformUrl,
        `/tenants/${tenantId}/inventory?${qs.toString()}`,
      );
      setInventory(data.items);
      pushLog(`Inventory returned ${data.items.length} numbers`);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      pushLog(`Inventory failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  async function purchaseSelected() {
    if (!tenantId || !selectedPurchase) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api<{ phone_number: PhoneNumber }>(
        platformUrl,
        `/tenants/${tenantId}/phone-numbers/purchase`,
        {
          method: "POST",
          headers: {
            "Idempotency-Key": crypto.randomUUID(),
          },
          body: JSON.stringify({
            phone_number: selectedPurchase,
            confirm: true,
          }),
        },
      );
      setPhoneNumberId(data.phone_number.id);
      pushLog(`Purchased ${data.phone_number.e164}`);
      await refreshNumbers();
      setStep(2);
    } catch (err) {
      const msg = (err as Error).message;
      setError(msg);
      pushLog(`Purchase failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell active="telephony">
      <header className="mx-auto max-w-2xl animate-[rise_420ms_ease-out] text-center">
        <h1 className="m-0 font-display text-[clamp(2rem,5vw,3rem)] font-semibold tracking-tight">
          Telephony setup
        </h1>
        <p className="mt-3 text-base text-text-secondary">
          Connect an existing Twilio number or purchase a new one. Activation
          requires a real inbound verification call — progress comes from the
          platform API.
        </p>
      </header>

      <ol className="mx-auto flex w-full max-w-2xl flex-wrap items-center justify-center gap-2">
        {STEPS.map((s, i) => (
          <li key={s.id} className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setStep(i)}
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors duration-200",
                i === step
                  ? "border-brand bg-brand-soft text-brand-bright"
                  : i < step
                    ? "border-border bg-surface-strong text-text-primary"
                    : "border-border text-text-muted",
              )}
            >
              <span
                className={cn(
                  "grid size-5 place-items-center rounded-full text-[10px]",
                  i < step ? "bg-brand text-background" : "bg-surface-strong",
                )}
              >
                {i < step ? <Check className="size-3" /> : i + 1}
              </span>
              {s.label}
            </button>
            {i < STEPS.length - 1 ? (
              <span className="hidden text-text-muted sm:inline" aria-hidden>
                ·
              </span>
            ) : null}
          </li>
        ))}
      </ol>

      {error ? (
        <div className="mx-auto w-full max-w-2xl">
          <ErrorBanner message={error} />
        </div>
      ) : null}

      <section className="glass-panel mx-auto w-full max-w-2xl p-5 sm:p-6">
        {step === 0 ? (
          <div className="grid gap-4">
            <h2 className="m-0 font-display text-xl font-semibold">
              Number option
            </h2>
            <p className="m-0 text-sm text-text-secondary">
              Choose how this tenant will obtain a phone number.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              {(
                [
                  {
                    id: "existing" as const,
                    title: "Connect existing",
                    body: "Use a Twilio number you already own.",
                    icon: Phone,
                  },
                  {
                    id: "purchase" as const,
                    title: "Purchase new",
                    body: "Search inventory and buy via the platform.",
                    icon: Radio,
                  },
                ] as const
              ).map((opt) => {
                const Icon = opt.icon;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setPath(opt.id)}
                    className={cn(
                      "rounded-xl border p-4 text-left transition-colors duration-200",
                      path === opt.id
                        ? "border-brand bg-brand-soft"
                        : "border-border bg-surface-strong hover:border-brand/40",
                    )}
                  >
                    <Icon className="mb-2 size-5 text-brand" aria-hidden />
                    <p className="font-semibold text-text-primary">{opt.title}</p>
                    <p className="mt-1 text-sm text-text-secondary">{opt.body}</p>
                  </button>
                );
              })}
            </div>
            <div className="flex justify-end">
              <Button onClick={() => setStep(1)}>
                Continue
                <ChevronRight className="size-4" aria-hidden />
              </Button>
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="grid gap-4">
            <h2 className="m-0 font-display text-xl font-semibold">Provider</h2>
            <p className="m-0 text-sm text-text-secondary">
              Point at the platform API and select or create a tenant.
            </p>
            <Field label="Platform API URL">
              <TextInput
                value={platformUrl}
                onChange={(e) => setPlatformUrl(e.target.value)}
                placeholder="http://127.0.0.1:8000"
              />
            </Field>
            <Field label="Tenant ID">
              <TextInput
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="uuid"
              />
            </Field>
            <form
              className="grid gap-3 rounded-xl border border-border bg-surface-strong/50 p-3 sm:grid-cols-[1fr_1fr_auto]"
              onSubmit={createTenant}
            >
              <TextInput
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                placeholder="Tenant name"
                required
              />
              <TextInput
                value={tenantSlug}
                onChange={(e) => setTenantSlug(e.target.value)}
                placeholder="slug"
                required
              />
              <Button type="submit" disabled={busy} variant="secondary">
                {busy ? <Loader2 className="size-4 animate-spin" /> : null}
                Create
              </Button>
            </form>
            <div className="flex justify-between gap-2">
              <Button variant="ghost" onClick={() => setStep(0)}>
                <ChevronLeft className="size-4" />
                Back
              </Button>
              <Button onClick={() => setStep(2)} disabled={!canAct}>
                Continue
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="grid gap-4">
            <h2 className="m-0 font-display text-xl font-semibold">
              Configuration
            </h2>
            {path === "existing" ? (
              <>
                <form className="grid gap-3" onSubmit={connectExisting}>
                  <Field label="Existing Twilio number (E.164)">
                    <TextInput
                      value={connectNumber}
                      onChange={(e) => setConnectNumber(e.target.value)}
                      placeholder="+15551234567"
                      required
                    />
                  </Field>
                  <Button type="submit" disabled={busy || !canAct}>
                    {busy ? <Loader2 className="size-4 animate-spin" /> : null}
                    Generate LiveKit config
                  </Button>
                </form>
                <form className="grid gap-3" onSubmit={confirmTrunk}>
                  <Field label="Phone number ID">
                    <TextInput
                      value={phoneNumberId}
                      onChange={(e) => setPhoneNumberId(e.target.value)}
                      placeholder="phone_number_id"
                    />
                  </Field>
                  <Field label="Twilio trunk SID (optional)">
                    <TextInput
                      value={twilioTrunkSid}
                      onChange={(e) => setTwilioTrunkSid(e.target.value)}
                      placeholder="TK…"
                    />
                  </Field>
                  <Button
                    type="submit"
                    variant="secondary"
                    disabled={busy || !canAct || !phoneNumberId}
                  >
                    Confirm trunk
                  </Button>
                </form>
                {setupSteps ? (
                  <pre className="m-0 max-h-56 overflow-auto rounded-xl border border-border bg-surface-strong p-3 text-xs text-text-secondary">
                    {JSON.stringify(setupSteps, null, 2)}
                  </pre>
                ) : null}
              </>
            ) : (
              <>
                <form
                  className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]"
                  onSubmit={searchInventory}
                >
                  <TextInput
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    placeholder="US"
                  />
                  <TextInput
                    value={areaCode}
                    onChange={(e) => setAreaCode(e.target.value)}
                    placeholder="Area code"
                  />
                  <Button type="submit" disabled={busy || !canAct}>
                    Search
                  </Button>
                </form>
                <ul className="m-0 grid list-none gap-2 p-0">
                  {inventory.map((item) => (
                    <li key={item.e164}>
                      <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-border bg-surface-strong px-3 py-2.5 text-sm">
                        <input
                          type="radio"
                          name="purchase"
                          value={item.e164}
                          checked={selectedPurchase === item.e164}
                          onChange={() => setSelectedPurchase(item.e164)}
                        />
                        <span className="text-text-primary">
                          {item.e164}
                          {item.locality ? ` · ${item.locality}` : ""}
                          {item.monthly_price
                            ? ` · ${item.monthly_price} ${item.price_unit || ""}`
                            : ""}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
                {inventory.length === 0 ? (
                  <EmptyHint>
                    Search inventory to see available numbers from the platform.
                  </EmptyHint>
                ) : null}
                <Button
                  disabled={busy || !canAct || !selectedPurchase}
                  onClick={purchaseSelected}
                >
                  Confirm purchase
                </Button>
              </>
            )}
            <div className="flex justify-between gap-2">
              <Button variant="ghost" onClick={() => setStep(1)}>
                <ChevronLeft className="size-4" />
                Back
              </Button>
              <Button
                onClick={() => setStep(3)}
                disabled={!phoneNumberId}
              >
                Continue
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="grid gap-4">
            <h2 className="m-0 font-display text-xl font-semibold">Test</h2>
            <p className="m-0 text-sm text-text-secondary">
              Start verification for phone number{" "}
              <code className="text-brand-bright">{phoneNumberId || "—"}</code>.
              Instructions are returned by the platform.
            </p>
            <Button
              disabled={busy || !canAct || !phoneNumberId}
              onClick={startVerification}
            >
              {busy ? <Loader2 className="size-4 animate-spin" /> : null}
              Start verification
            </Button>
            <div className="flex justify-between gap-2">
              <Button variant="ghost" onClick={() => setStep(2)}>
                <ChevronLeft className="size-4" />
                Back
              </Button>
              <Button onClick={() => setStep(4)}>
                Continue
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="grid gap-4">
            <h2 className="m-0 font-display text-xl font-semibold">
              Activation
            </h2>
            <p className="m-0 text-sm text-text-secondary">
              Numbers activate only after a successful inbound verification
              call. Refresh to read live connection and verification status.
            </p>
            <Button
              variant="secondary"
              disabled={!canAct || busy}
              onClick={() =>
                refreshNumbers().catch((err) => {
                  setError((err as Error).message);
                })
              }
            >
              Refresh numbers
            </Button>
            <ul className="m-0 grid list-none gap-2 p-0">
              {numbers.map((n) => (
                <li
                  key={n.id}
                  className="rounded-xl border border-border bg-surface-strong px-3 py-3 text-sm"
                >
                  <p className="font-mono text-text-primary">{n.e164}</p>
                  <p className="mt-1 text-text-secondary">
                    Connection: {n.connection_status} · Verification:{" "}
                    {n.verification_status}
                    {n.provisioning_state
                      ? ` · Provisioning: ${n.provisioning_state}`
                      : ""}
                  </p>
                </li>
              ))}
            </ul>
            {numbers.length === 0 ? (
              <EmptyHint>No numbers returned yet for this tenant.</EmptyHint>
            ) : null}
            <div>
              <p className="mb-2 text-xs tracking-wide text-text-muted uppercase">
                Activity log
              </p>
              <pre className="m-0 max-h-48 overflow-auto rounded-xl border border-border bg-surface-strong p-3 text-xs text-text-secondary">
                {log || "No activity yet."}
              </pre>
            </div>
            <div className="flex justify-between gap-2">
              <Button variant="ghost" onClick={() => setStep(3)}>
                <ChevronLeft className="size-4" />
                Back
              </Button>
            </div>
          </div>
        ) : null}
      </section>
    </PageShell>
  );
}

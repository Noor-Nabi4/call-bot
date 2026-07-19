"use client";

import { FormEvent, useMemo, useState } from "react";

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

const inputClass =
  "w-full rounded border border-line bg-white px-3 py-2.5 font-sans text-ink";
const buttonClass =
  "justify-self-start rounded border-0 bg-live px-4 py-2.5 font-sans font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50";
const panelClass =
  "relative z-[1] grid gap-3.5 border-t border-line py-5";
const preClass =
  "m-0 max-h-72 overflow-auto rounded border border-line bg-white p-3.5 text-[0.85rem]";

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
  const [platformUrl, setPlatformUrl] = useState(defaultPlatformUrl);
  const [tenantId, setTenantId] = useState("");
  const [tenantName, setTenantName] = useState("Acme HVAC");
  const [tenantSlug, setTenantSlug] = useState("acme-hvac");
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

  const canAct = useMemo(() => Boolean(platformUrl && tenantId), [platformUrl, tenantId]);

  function pushLog(message: string) {
    setLog((prev) => `${new Date().toISOString()}  ${message}\n${prev}`);
  }

  async function createTenant(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const tenant = await api<{ id: string }>(platformUrl, "/tenants", {
        method: "POST",
        body: JSON.stringify({ name: tenantName, slug: tenantSlug }),
      });
      setTenantId(tenant.id);
      pushLog(`Created tenant ${tenant.id}`);
    } catch (err) {
      pushLog(`Create tenant failed: ${(err as Error).message}`);
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
    } catch (err) {
      pushLog(`Connect failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirmTrunk(e: FormEvent) {
    e.preventDefault();
    if (!tenantId || !phoneNumberId) return;
    setBusy(true);
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
    } catch (err) {
      pushLog(`Confirm trunk failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function startVerification() {
    if (!tenantId || !phoneNumberId) return;
    setBusy(true);
    try {
      const data = await api<{ instructions: string }>(
        platformUrl,
        `/tenants/${tenantId}/phone-numbers/${phoneNumberId}/verification/start`,
        { method: "POST" },
      );
      pushLog(data.instructions);
      await refreshNumbers();
    } catch (err) {
      pushLog(`Verification start failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function searchInventory(e: FormEvent) {
    e.preventDefault();
    if (!tenantId) return;
    setBusy(true);
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
      pushLog(`Inventory failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function purchaseSelected() {
    if (!tenantId || !selectedPurchase) return;
    setBusy(true);
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
    } catch (err) {
      pushLog(`Purchase failed: ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative isolate grid min-h-screen grid-rows-[auto_1fr_auto] gap-6 overflow-hidden p-[clamp(1.5rem,4vw,3.5rem)] sm:gap-8">
      <div
        className="atmosphere absolute inset-0 -z-10 bg-[radial-gradient(circle_at_12%_18%,rgba(15,118,110,0.16),transparent_42%),radial-gradient(circle_at_88%_8%,rgba(16,35,58,0.1),transparent_36%),linear-gradient(160deg,#f7fafb_0%,#edf3f6_48%,#e7eef2_100%)]"
        aria-hidden
      />
      <header className="max-w-xl animate-rise">
        <p className="mb-3 font-display text-[clamp(2.4rem,6vw,4.2rem)] font-[650] leading-[0.95] tracking-[-0.04em]">
          Call Bot
        </p>
        <h1 className="m-0 text-[clamp(1.1rem,2vw,1.35rem)] font-semibold tracking-[0.08em] text-live-deep uppercase">
          Telephony wizard
        </h1>
        <p className="mt-4 max-w-lg text-lg leading-relaxed text-ink-soft">
          Path A: connect an existing Twilio number. Path B: search and purchase
          via the platform Twilio account. Numbers activate only after an inbound
          verification call.
        </p>
        <p className="mt-3">
          <a href="/" className="underline-offset-2 hover:underline">
            ← Back to voice playground
          </a>
        </p>
      </header>

      <section className={panelClass}>
        <h2>Platform</h2>
        <label className="grid gap-1.5 text-[0.95rem] text-ink-soft">
          Platform API URL
          <input
            className={inputClass}
            value={platformUrl}
            onChange={(e) => setPlatformUrl(e.target.value)}
            placeholder="http://127.0.0.1:8000"
          />
        </label>
        <label className="grid gap-1.5 text-[0.95rem] text-ink-soft">
          Tenant ID
          <input
            className={inputClass}
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="uuid"
          />
        </label>
        <form
          className="grid grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] items-end gap-2.5"
          onSubmit={createTenant}
        >
          <input
            className={inputClass}
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            placeholder="Tenant name"
          />
          <input
            className={inputClass}
            value={tenantSlug}
            onChange={(e) => setTenantSlug(e.target.value)}
            placeholder="slug"
          />
          <button type="submit" className={buttonClass} disabled={busy}>
            Create tenant
          </button>
        </form>
      </section>

      <section className={panelClass}>
        <h2>Path A — Connect existing</h2>
        <form className="grid gap-3.5" onSubmit={connectExisting}>
          <label className="grid gap-1.5 text-[0.95rem] text-ink-soft">
            Existing Twilio number (E.164)
            <input
              className={inputClass}
              value={connectNumber}
              onChange={(e) => setConnectNumber(e.target.value)}
              placeholder="+15551234567"
              required
            />
          </label>
          <button type="submit" className={buttonClass} disabled={busy || !canAct}>
            Generate LiveKit config
          </button>
        </form>
        <form
          className="grid grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] items-end gap-2.5"
          onSubmit={confirmTrunk}
        >
          <input
            className={inputClass}
            value={phoneNumberId}
            onChange={(e) => setPhoneNumberId(e.target.value)}
            placeholder="phone_number_id"
          />
          <input
            className={inputClass}
            value={twilioTrunkSid}
            onChange={(e) => setTwilioTrunkSid(e.target.value)}
            placeholder="Twilio trunk SID (optional)"
          />
          <button
            type="submit"
            className={buttonClass}
            disabled={busy || !canAct || !phoneNumberId}
          >
            Confirm trunk
          </button>
        </form>
        <button
          type="button"
          className={buttonClass}
          disabled={busy || !canAct || !phoneNumberId}
          onClick={startVerification}
        >
          Start verification
        </button>
        {setupSteps ? (
          <pre className={preClass}>{JSON.stringify(setupSteps, null, 2)}</pre>
        ) : null}
      </section>

      <section className={panelClass}>
        <h2>Path B — Purchase</h2>
        <form
          className="grid grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] items-end gap-2.5"
          onSubmit={searchInventory}
        >
          <input
            className={inputClass}
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="US"
          />
          <input
            className={inputClass}
            value={areaCode}
            onChange={(e) => setAreaCode(e.target.value)}
            placeholder="Area code"
          />
          <button type="submit" className={buttonClass} disabled={busy || !canAct}>
            Search inventory
          </button>
        </form>
        <ul className="m-0 grid list-none gap-1.5 p-0">
          {inventory.map((item) => (
            <li key={item.e164}>
              <label className="flex items-center gap-2 text-[0.95rem] text-ink-soft">
                <input
                  type="radio"
                  name="purchase"
                  value={item.e164}
                  checked={selectedPurchase === item.e164}
                  onChange={() => setSelectedPurchase(item.e164)}
                />
                <span>
                  {item.e164}{" "}
                  {item.locality ? `(${item.locality})` : ""}{" "}
                  {item.monthly_price
                    ? `— ${item.monthly_price} ${item.price_unit || ""}`
                    : ""}
                </span>
              </label>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className={buttonClass}
          disabled={busy || !canAct || !selectedPurchase}
          onClick={purchaseSelected}
        >
          Confirm purchase
        </button>
      </section>

      <section className={panelClass}>
        <h2>Numbers</h2>
        <button
          type="button"
          className={buttonClass}
          disabled={!canAct || busy}
          onClick={refreshNumbers}
        >
          Refresh
        </button>
        <ul>
          {numbers.map((n) => (
            <li key={n.id}>
              {n.e164} — {n.connection_status}/{n.verification_status}
            </li>
          ))}
        </ul>
      </section>

      <section className={panelClass}>
        <h2>Log</h2>
        <pre className={preClass}>{log || "No activity yet."}</pre>
      </section>
    </main>
  );
}

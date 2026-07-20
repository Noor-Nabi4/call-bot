"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Phone, Search, Link2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  assignPhoneProfile,
  confirmPhoneTrunk,
  connectPhoneNumber,
  createTestCall,
  ensureTwilioSubaccount,
  listAgentProfiles,
  listPhoneNumbers,
  purchasePhoneNumber,
  searchInventory,
  startPhoneVerification,
  type AgentProfile,
  type InventoryNumber,
  type PhoneNumber,
} from "@/lib/api";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Surface,
  useToast,
} from "@/components/ui";

export default function PhonesPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [phones, setPhones] = useState<PhoneNumber[]>([]);
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [inventory, setInventory] = useState<InventoryNumber[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [areaCode, setAreaCode] = useState("");
  const [connectNumber, setConnectNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [testInfo, setTestInfo] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [phoneData, profileData] = await Promise.all([
      listPhoneNumbers(),
      listAgentProfiles(),
    ]);
    setPhones(phoneData.items);
    setProfiles(profileData.profiles);
  }, []);

  useEffect(() => {
    if (!user) return;
    setFetching(true);
    load()
      .catch((err) => setError(safeUserError(err, "Could not load phones")))
      .finally(() => setFetching(false));
  }, [user, load]);

  async function onAssign(phoneId: string, profileId: string) {
    try {
      await assignPhoneProfile(phoneId, profileId || null);
      toast.push("Phone routing updated", "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Could not assign agent"), "error");
    }
  }

  async function onConnect() {
    if (!connectNumber.trim()) return;
    setBusy(true);
    try {
      await connectPhoneNumber({ phone_number: connectNumber.trim() });
      toast.push("Number connected — confirm trunk next", "success");
      setConnectNumber("");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Could not connect number"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onSearch() {
    setBusy(true);
    try {
      await ensureTwilioSubaccount();
      const data = await searchInventory({
        country: "US",
        area_code: areaCode || undefined,
        limit: 10,
      });
      setInventory(data.items || []);
    } catch (err) {
      toast.push(safeUserError(err, "Inventory search failed"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onPurchase(e164: string) {
    setBusy(true);
    try {
      await purchasePhoneNumber(e164, crypto.randomUUID());
      toast.push(`Purchased ${e164}`, "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Purchase failed"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm(phoneId: string) {
    try {
      await confirmPhoneTrunk(phoneId);
      toast.push("Trunk confirmed", "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Confirm failed"), "error");
    }
  }

  async function onVerify(phoneId: string) {
    try {
      await startPhoneVerification(phoneId);
      toast.push("Verification started — place a test inbound call", "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Verification failed"), "error");
    }
  }

  async function onTest(profileId?: string | null) {
    try {
      const session = await createTestCall(profileId);
      setTestInfo(
        `Test room ${session.room_name} ready at ${session.server_url} for profile ${session.agent_profile_id}.`,
      );
      toast.push("Test call ready", "success");
    } catch (err) {
      toast.push(safeUserError(err, "Test call failed"), "error");
    }
  }

  const defaultProfile = profiles.find((p) => p.is_default);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Phones"
        description="Buy or connect numbers, assign each DID to an Agent Profile, and run test calls. Advanced recording and forwarding come later."
        actions={
          <Link href="/agents">
            <Button variant="secondary" size="sm">
              Agent builder
            </Button>
          </Link>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}
      {testInfo ? (
        <p className="mt-3 rounded-lg border border-brand/30 bg-brand-soft px-3 py-2 text-sm">
          {testInfo}
        </p>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Surface className="ops-surface-rise p-5">
          <div className="mb-4 flex items-center gap-2">
            <Phone className="size-4 text-brand" aria-hidden />
            <h2 className="font-heading text-lg font-semibold">Inventory</h2>
          </div>
          {defaultProfile ? (
            <p className="mb-3 text-xs text-text-muted">
              Default fallback agent: <strong>{defaultProfile.name}</strong>
            </p>
          ) : (
            <p className="mb-3 text-xs text-warn">
              No default agent profile — create one before SIP calls.
            </p>
          )}
          {fetching ? (
            <LoadingSkeleton rows={4} />
          ) : phones.length === 0 ? (
            <p className="text-sm text-text-muted">No phone numbers yet.</p>
          ) : (
            <ul className="space-y-3">
              {phones.map((phone) => (
                <li
                  key={phone.id}
                  className="rounded-xl border border-border bg-paper/60 p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{phone.e164}</p>
                      <p className="text-xs text-text-muted">
                        {phone.connection_status} · {phone.verification_status}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        onTest(
                          phone.effective_agent_profile_id ||
                            phone.agent_profile_id,
                        )
                      }
                    >
                      Test call
                    </Button>
                  </div>
                  <div className="mt-3">
                    <Field label="Assigned agent">
                      <Select
                        value={phone.agent_profile_id || ""}
                        onChange={(e) => onAssign(phone.id, e.target.value)}
                      >
                        <option value="">
                          Default
                          {defaultProfile ? ` (${defaultProfile.name})` : ""}
                        </option>
                        {profiles.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onConfirm(phone.id)}
                    >
                      Confirm trunk
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => onVerify(phone.id)}
                    >
                      Start verification
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Surface>

        <div className="space-y-6">
          <Surface className="ops-surface-rise p-5">
            <div className="mb-4 flex items-center gap-2">
              <Link2 className="size-4 text-brand" aria-hidden />
              <h2 className="font-heading text-lg font-semibold">
                Connect existing
              </h2>
            </div>
            <Field label="E.164 number">
              <Input
                value={connectNumber}
                onChange={(e) => setConnectNumber(e.target.value)}
                placeholder="+15551234567"
              />
            </Field>
            <Button className="mt-3" onClick={onConnect} disabled={busy}>
              Connect Twilio number
            </Button>
          </Surface>

          <Surface className="ops-surface-rise p-5">
            <div className="mb-4 flex items-center gap-2">
              <Search className="size-4 text-brand" aria-hidden />
              <h2 className="font-heading text-lg font-semibold">Buy number</h2>
            </div>
            <div className="flex gap-2">
              <Field label="Area code">
                <Input
                  value={areaCode}
                  onChange={(e) => setAreaCode(e.target.value)}
                  placeholder="415"
                />
              </Field>
              <div className="flex items-end">
                <Button onClick={onSearch} disabled={busy}>
                  Search
                </Button>
              </div>
            </div>
            <ul className="mt-3 divide-y divide-border">
              {inventory.map((item) => (
                <li
                  key={item.e164}
                  className="flex items-center justify-between gap-2 py-2 text-sm"
                >
                  <span>
                    {item.e164}
                    {item.locality ? ` · ${item.locality}` : ""}
                    {item.monthly_price ? ` · ${item.monthly_price}` : ""}
                  </span>
                  <Button
                    size="sm"
                    disabled={busy}
                    onClick={() => onPurchase(item.e164)}
                  >
                    Buy
                  </Button>
                </li>
              ))}
            </ul>
          </Surface>
        </div>
      </div>
    </AppShell>
  );
}

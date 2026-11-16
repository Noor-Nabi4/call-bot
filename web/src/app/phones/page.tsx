"use client";

import Link from "next/link";
import { FormEvent, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Phone, Plus, Search, Link2 } from "lucide-react";
import { AppShell, OnboardingShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { ONBOARDING_PATH } from "@/lib/onboarding";
import {
  assignPhoneProfile,
  confirmPhoneTrunk,
  connectPhoneNumber,
  createTestCall,
  ensureTwilioSubaccount,
  listAgentProfiles,
  listPhoneNumbers,
  purchasePhoneNumber,
  releasePhoneNumber,
  searchInventory,
  startPhoneVerification,
  type AgentProfile,
  type InventoryNumber,
  type PhoneNumber,
  type PhoneVerificationStart,
} from "@/lib/api";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ConfirmDialog,
  DetailDrawer,
  EmptyState,
  ErrorState,
  ForbiddenState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Surface,
  useToast,
} from "@/components/ui";

const CONNECT_FORM_ID = "connect-phone-form";
const BUY_FORM_ID = "buy-phone-form";

export default function PhonesPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <PhonesPageInner />
    </Suspense>
  );
}

function PhonesPageInner() {
  const searchParams = useSearchParams();
  const fromOnboarding = searchParams.get("from") === "onboarding";
  const setupAction = searchParams.get("action");
  const { user, loading, forbidden } = useAuth({
    permission: "phones.manage",
    // Required during mandatory onboarding before COMPLETED.
    allowIncompleteOnboarding: true,
  });
  const toast = useToast();
  const [phones, setPhones] = useState<PhoneNumber[]>([]);
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [inventory, setInventory] = useState<InventoryNumber[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [areaCode, setAreaCode] = useState("");
  const [connectNumber, setConnectNumber] = useState("");
  const [connectOpen, setConnectOpen] = useState(false);
  const [buyOpen, setBuyOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [testInfo, setTestInfo] = useState<string | null>(null);
  const [verifyInfo, setVerifyInfo] = useState<PhoneVerificationStart | null>(
    null,
  );
  const [purchaseTarget, setPurchaseTarget] = useState<InventoryNumber | null>(
    null,
  );
  const [releaseTarget, setReleaseTarget] = useState<PhoneNumber | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  const load = useCallback(async () => {
    const phoneData = await listPhoneNumbers();
    setPhones(phoneData.items);
    const stillPending = phoneData.items.some(
      (p) =>
        p.verification_status === "pending" ||
        p.connection_status === "pending_verification",
    );
    if (!stillPending) setVerifyInfo(null);
    // Agent profiles may be gated until onboarding completes — non-fatal here.
    try {
      const profileData = await listAgentProfiles();
      setProfiles(profileData.profiles);
    } catch {
      setProfiles([]);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((err) => setError(safeUserError(err, "Could not load phones")))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  // Deep-link from onboarding CTAs: open connect or buy drawer once.
  useEffect(() => {
    if (!fromOnboarding || fetching || !user) return;
    if (setupAction === "connect") setConnectOpen(true);
    if (setupAction === "buy") setBuyOpen(true);
  }, [fromOnboarding, setupAction, fetching, user]);

  const Shell = fromOnboarding ? OnboardingShell : AppShell;

  async function onAssign(phoneId: string, profileId: string) {
    try {
      await assignPhoneProfile(phoneId, profileId || null);
      toast.push("Phone routing updated", "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Could not assign agent"), "error");
    }
  }

  const closeConnect = useCallback(() => {
    if (busy) return;
    setConnectOpen(false);
    setConnectNumber("");
  }, [busy]);

  const closeBuy = useCallback(() => {
    if (busy) return;
    setBuyOpen(false);
    setAreaCode("");
    setInventory([]);
  }, [busy]);

  async function onConnect(e: FormEvent) {
    e.preventDefault();
    if (!connectNumber.trim()) return;
    setBusy(true);
    try {
      await connectPhoneNumber({ phone_number: connectNumber.trim() });
      toast.push("Number connected — confirm trunk next", "success");
      setConnectNumber("");
      setConnectOpen(false);
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Could not connect number"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onSearch(e?: FormEvent) {
    e?.preventDefault();
    const digits = areaCode.replace(/\D+/g, "");
    const normalized =
      digits.length === 3
        ? digits
        : digits.length === 11 && digits.startsWith("1")
          ? digits.slice(1, 4)
          : digits.length >= 10
            ? digits.slice(0, 3)
            : digits;
    if (areaCode.trim() && !/^[2-9]\d{2}$/.test(normalized)) {
      toast.push("Enter a 3-digit area code (e.g. 415), not a full number", "error");
      return;
    }
    setBusy(true);
    try {
      await ensureTwilioSubaccount();
      const data = await searchInventory({
        country: "US",
        area_code: normalized || undefined,
        limit: 10,
      });
      setInventory(data.items || []);
      if (normalized && normalized !== areaCode.trim()) {
        setAreaCode(normalized);
      }
    } catch (err) {
      toast.push(safeUserError(err, "Inventory search failed"), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmPurchase() {
    if (!purchaseTarget) return;
    setConfirmBusy(true);
    try {
      await purchasePhoneNumber(purchaseTarget.e164, crypto.randomUUID());
      toast.push(`Purchased ${purchaseTarget.e164}`, "success");
      setPurchaseTarget(null);
      setInventory((prev) =>
        prev.filter((item) => item.e164 !== purchaseTarget.e164),
      );
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Purchase failed"), "error");
    } finally {
      setConfirmBusy(false);
    }
  }

  async function onConfirmRelease() {
    if (!releaseTarget) return;
    setConfirmBusy(true);
    try {
      await releasePhoneNumber(releaseTarget.id);
      toast.push(`Released ${releaseTarget.e164}`, "success");
      setReleaseTarget(null);
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Release failed"), "error");
    } finally {
      setConfirmBusy(false);
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
      const started = await startPhoneVerification(phoneId);
      setVerifyInfo(started);
      toast.push(
        `Call ${started.e164} from another phone to verify`,
        "success",
      );
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
  const activePhones = phones.filter((p) => p.connection_status !== "released");
  const pendingVerifyPhone =
    activePhones.find(
      (p) =>
        p.verification_status === "pending" ||
        p.connection_status === "pending_verification",
    ) ?? null;
  const verifyBanner =
    verifyInfo != null
      ? {
          e164: verifyInfo.e164,
          instructions: verifyInfo.instructions,
          expiresAt: verifyInfo.expires_at
            ? new Date(verifyInfo.expires_at).toLocaleString()
            : null,
        }
      : pendingVerifyPhone != null
        ? {
            e164: pendingVerifyPhone.e164,
            instructions: null as string | null,
            expiresAt: null as string | null,
          }
        : null;

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (forbidden) {
    return (
      <Shell user={user}>
        <ForbiddenState />
      </Shell>
    );
  }

  return (
    <Shell user={user}>
      {fromOnboarding ? (
        <div className="mb-4 rounded-lg border border-border bg-teal-soft/40 px-4 py-3 text-sm text-text-primary">
          Phone setup is required before dashboard access. Use{" "}
          <strong>Connect</strong> (Twilio number you already own) or{" "}
          <strong>Buy number</strong>, then verify. When status is ready,{" "}
          <Link
            href={`${ONBOARDING_PATH}?manual=1`}
            className="font-medium text-teal underline-offset-2 hover:underline"
          >
            return to onboarding
          </Link>{" "}
          and continue.
        </div>
      ) : null}
      <PageHeader
        title="Phones"
        description="Buy or connect numbers, assign each DID to an Agent Profile, and run test calls. Advanced recording and forwarding come later."
        actions={
          <div className="flex flex-wrap gap-2">
            {fromOnboarding ? (
              <Link href={`${ONBOARDING_PATH}?manual=1`}>
                <Button variant="secondary" size="sm">
                  Back to onboarding
                </Button>
              </Link>
            ) : null}
            <Link href="/agents">
              <Button variant="secondary" size="sm">
                Agent builder
              </Button>
            </Link>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setConnectOpen(true)}
            >
              <Link2 className="size-3.5" aria-hidden />
              Connect
            </Button>
            <Button size="sm" onClick={() => setBuyOpen(true)}>
              <Plus className="size-3.5" aria-hidden />
              Buy number
            </Button>
          </div>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}
      {verifyBanner ? (
        <div
          role="status"
          className="mt-4 rounded-lg border border-teal/40 bg-teal-soft px-4 py-3 text-sm text-text-primary"
        >
          <p className="font-semibold">Action required: verify this number</p>
          <p className="mt-1">
            Call{" "}
            <strong className="font-mono tracking-wide">
              {verifyBanner.e164}
            </strong>{" "}
            from another phone now. Keep the call connected until it rings or
            answers — we mark the number Active after we detect the inbound
            call.
          </p>
          {verifyBanner.expiresAt ? (
            <p className="mt-1 text-text-secondary">
              Complete this before {verifyBanner.expiresAt}.
            </p>
          ) : null}
          {verifyBanner.instructions ? (
            <p className="mt-2 text-text-secondary">{verifyBanner.instructions}</p>
          ) : null}
        </div>
      ) : null}
      {testInfo ? (
        <p className="mt-3 rounded-lg border border-brand/30 bg-brand-soft px-3 py-2 text-sm">
          {testInfo}
        </p>
      ) : null}

      <div className="mt-6">
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
        ) : activePhones.length === 0 ? (
          <EmptyState
            icon={<Phone className="size-8" />}
            title="No phone numbers yet"
            description="Connect an existing Twilio number or buy a new one."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setConnectOpen(true)}
                >
                  Connect
                </Button>
                <Button size="sm" onClick={() => setBuyOpen(true)}>
                  Buy number
                </Button>
              </div>
            }
          />
        ) : (
          <Surface className="ops-surface-rise p-5">
            <div className="mb-4 flex items-center gap-2">
              <Phone className="size-4 text-brand" aria-hidden />
              <h2 className="font-heading text-lg font-semibold">Inventory</h2>
            </div>
            <ul className="space-y-3">
              {activePhones.map((phone) => (
                <li
                  key={phone.id}
                  className="rounded-xl border border-border bg-paper/60 p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-medium">{phone.e164}</p>
                      <p className="text-xs text-text-muted">
                        {phone.connection_status} · {phone.verification_status}
                        {phone.onboarding_path
                          ? ` · ${phone.onboarding_path}`
                          : ""}
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
                  {phone.verification_status === "pending" ||
                  phone.connection_status === "pending_verification" ? (
                    <p className="mt-2 rounded-md border border-teal/30 bg-teal-soft/60 px-2.5 py-2 text-xs text-text-primary">
                      Call <strong className="font-mono">{phone.e164}</strong>{" "}
                      from another phone to finish verification.
                    </p>
                  ) : null}
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
                    {phone.can_release ? (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => setReleaseTarget(phone)}
                      >
                        Release
                      </Button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </Surface>
        )}
      </div>

      <DetailDrawer
        open={connectOpen}
        onClose={closeConnect}
        title="Connect existing number"
        description="Link a Twilio number you already own. Confirm the trunk after connecting."
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeConnect} disabled={busy}>
              Cancel
            </Button>
            <Button
              form={CONNECT_FORM_ID}
              type="submit"
              disabled={busy || !connectNumber.trim()}
            >
              {busy ? "Connecting…" : "Connect"}
            </Button>
          </div>
        }
      >
        <form id={CONNECT_FORM_ID} onSubmit={onConnect} className="grid gap-3">
          <Field label="E.164 number">
            <Input
              value={connectNumber}
              onChange={(e) => setConnectNumber(e.target.value)}
              placeholder="+15551234567"
              required
            />
          </Field>
        </form>
      </DetailDrawer>

      <DetailDrawer
        open={buyOpen}
        onClose={closeBuy}
        title="Buy number"
        description="Search by 3-digit US area code (e.g. 415), then confirm purchase."
        width="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeBuy} disabled={busy}>
              Close
            </Button>
          </div>
        }
      >
        <form id={BUY_FORM_ID} onSubmit={onSearch} className="grid gap-3">
          <div className="flex gap-2">
            <Field label="Area code (3 digits)" className="flex-1">
              <Input
                value={areaCode}
                onChange={(e) => setAreaCode(e.target.value)}
                placeholder="415"
                inputMode="numeric"
                maxLength={14}
                aria-describedby="area-code-hint"
              />
            </Field>
            <div className="flex items-end">
              <Button type="submit" disabled={busy}>
                <Search className="size-3.5" aria-hidden />
                {busy ? "Searching…" : "Search"}
              </Button>
            </div>
          </div>
          <p id="area-code-hint" className="text-xs text-text-muted">
            Example: 415. Do not paste a full phone number.
          </p>
          <ul className="divide-y divide-border">
            {inventory.length === 0 ? (
              <li className="py-6 text-center text-sm text-text-muted">
                Search to see available numbers.
              </li>
            ) : (
              inventory.map((item) => (
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
                    disabled={busy || confirmBusy}
                    onClick={() => setPurchaseTarget(item)}
                  >
                    Buy
                  </Button>
                </li>
              ))
            )}
          </ul>
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={!!purchaseTarget}
        title="Buy this number?"
        description={
          purchaseTarget
            ? `${purchaseTarget.e164}${
                purchaseTarget.monthly_price
                  ? ` (${purchaseTarget.monthly_price}/mo)`
                  : ""
              } will be purchased on your Twilio subaccount and provisioned for inbound SIP.`
            : undefined
        }
        confirmLabel="Buy number"
        busy={confirmBusy}
        onConfirm={() => {
          void onConfirmPurchase();
        }}
        onCancel={() => {
          if (confirmBusy) return;
          setPurchaseTarget(null);
        }}
      />

      <ConfirmDialog
        open={!!releaseTarget}
        title="Release this number?"
        description={
          releaseTarget
            ? `${releaseTarget.e164} will be released from Twilio and removed from inbound routing. This cannot be undone.`
            : undefined
        }
        confirmLabel="Release"
        danger
        busy={confirmBusy}
        onConfirm={() => {
          void onConfirmRelease();
        }}
        onCancel={() => {
          if (confirmBusy) return;
          setReleaseTarget(null);
        }}
      />
    </Shell>
  );
}

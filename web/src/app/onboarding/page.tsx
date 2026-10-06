"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  progressLabel,
  resumeTarget,
  type OnboardingState,
} from "@/lib/onboarding";
import {
  Button,
  ErrorState,
  Field,
  ForbiddenState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  Surface,
  useToast,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type CatalogOption = { key: string; name: string; description?: string };

type BusinessProfile = {
  business_name?: string | null;
  industry?: string | null;
  country?: string | null;
  state?: string | null;
  timezone?: string | null;
  currency?: string | null;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  business_size?: string | null;
  business_type?: string | null;
  business_model?: string | null;
};

type CrmConfiguration = {
  template_key?: string;
  modules?: { key: string; enabled: boolean }[];
  setup_completed?: boolean;
} | null;

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let message = errors.saveFailed;
    try {
      const body = await res.json();
      message = body?.detail?.message || body?.detail || message;
    } catch {
      /* ignore */
    }
    throw new Error(typeof message === "string" ? message : errors.saveFailed);
  }
  return res.json();
}

const WIZARD_STEPS = [
  "business_profile",
  "industry",
  "business_model",
  "catalog",
  "customers",
  "business_hours",
  "ai_configuration",
  "review",
] as const;

export default function OnboardingPage() {
  const { user, loading, forbidden } = useAuth({
    permission: "organization.read",
  });
  const canUpdate = Boolean(
    user?.permissions?.some((p) => p.key === "organization.update"),
  );
  const toast = useToast();
  const [onboarding, setOnboarding] = useState<OnboardingState | null>(null);
  const [profile, setProfile] = useState<BusinessProfile>({});
  const [industries, setIndustries] = useState<CatalogOption[]>([]);
  const [models, setModels] = useState<CatalogOption[]>([]);
  const [sizes, setSizes] = useState<CatalogOption[]>([]);
  const [crm, setCrm] = useState<CrmConfiguration>(null);
  const [previewModules, setPreviewModules] = useState<string[]>([]);
  const [activeStep, setActiveStep] = useState<string>("business_profile");
  const [fetching, setFetching] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [ob, bp, cfg] = await Promise.all([
      api<{ onboarding: OnboardingState }>("/api/admin/organization/onboarding"),
      api<{
        profile: BusinessProfile;
        catalogs: {
          industries: CatalogOption[];
          business_models: CatalogOption[];
          business_sizes: CatalogOption[];
        };
      }>("/api/admin/organization/business-profile"),
      api<{
        configuration: CrmConfiguration;
        preview_template: { modules: string[] };
      }>("/api/admin/organization/crm-configuration"),
    ]);
    setOnboarding(ob.onboarding);
    setProfile(bp.profile || {});
    setIndustries(bp.catalogs.industries || []);
    setModels(bp.catalogs.business_models || []);
    setSizes(bp.catalogs.business_sizes || []);
    setCrm(cfg.configuration);
    setPreviewModules(cfg.preview_template?.modules || []);
    const resume = resumeTarget(ob.onboarding);
    setActiveStep(resume || "business_profile");
    setLoadError(null);
  }, []);

  useEffect(() => {
    if (!user) return;
    load()
      .catch((e) => setLoadError(safeUserError(e, errors.loadFailed)))
      .finally(() => setFetching(false));
  }, [user, load]);

  const closed =
    onboarding?.status === "COMPLETED" || onboarding?.status === "SKIPPED";

  const stepIndex = useMemo(
    () => Math.max(0, WIZARD_STEPS.indexOf(activeStep as (typeof WIZARD_STEPS)[number])),
    [activeStep],
  );

  async function saveProfile(completeSteps: string[]) {
    if (!canUpdate) return;
    setBusy(true);
    try {
      const data = await api<{
        profile: BusinessProfile;
        onboarding?: OnboardingState;
      }>("/api/admin/organization/business-profile", {
        method: "PATCH",
        body: JSON.stringify({
          business_name: profile.business_name || null,
          industry: profile.industry || null,
          country: profile.country || null,
          state: profile.state || null,
          timezone: profile.timezone || "UTC",
          currency: profile.currency || "USD",
          website: profile.website || null,
          phone: profile.phone || null,
          email: profile.email || null,
          business_size: profile.business_size || null,
          business_type: profile.business_type || null,
          complete_steps: completeSteps,
        }),
      });
      setProfile(data.profile);
      if (data.onboarding) setOnboarding(data.onboarding);
      toast.push("Saved", "success");
      await refreshCrm();
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function saveModel() {
    if (!canUpdate || !profile.business_type) return;
    setBusy(true);
    try {
      const data = await api<{
        business_model: string;
        onboarding: OnboardingState;
      }>("/api/admin/organization/business-model", {
        method: "PUT",
        body: JSON.stringify({ business_model: profile.business_type }),
      });
      setProfile((p) => ({
        ...p,
        business_type: data.business_model,
        business_model: data.business_model,
      }));
      setOnboarding(data.onboarding);
      toast.push("Business model saved", "success");
      await refreshCrm();
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function completeOrSkip(step: string, skip = false) {
    if (!canUpdate) return;
    setBusy(true);
    try {
      const path = skip
        ? `/api/admin/organization/onboarding/steps/${step}/skip`
        : `/api/admin/organization/onboarding/steps/${step}/complete`;
      const data = await api<{ onboarding: OnboardingState }>(path, {
        method: "POST",
      });
      setOnboarding(data.onboarding);
      const next = resumeTarget(data.onboarding);
      if (next) setActiveStep(next);
      toast.push(skip ? "Step skipped" : "Step completed", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function finishOnboarding() {
    if (!canUpdate) return;
    setBusy(true);
    try {
      // Ensure review is marked complete then finalize
      await api("/api/admin/organization/onboarding/steps/review/complete", {
        method: "POST",
      });
      const data = await api<{ onboarding: OnboardingState }>(
        "/api/admin/organization/onboarding/complete",
        { method: "POST" },
      );
      setOnboarding(data.onboarding);
      await refreshCrm();
      toast.push("Onboarding completed", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function refreshCrm() {
    const cfg = await api<{
      configuration: CrmConfiguration;
      preview_template: { modules: string[] };
    }>("/api/admin/organization/crm-configuration");
    setCrm(cfg.configuration);
    setPreviewModules(cfg.preview_template?.modules || []);
  }

  function go(delta: number) {
    const next = WIZARD_STEPS[stepIndex + delta];
    if (next) setActiveStep(next);
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }
  if (forbidden) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Business onboarding"
        description="Configure your organization profile, industry, business model, and CRM modules."
      />

      {fetching ? (
        <LoadingSkeleton rows={8} />
      ) : loadError ? (
        <ErrorState
          title="Could not load onboarding"
          message={loadError}
          onRetry={() => {
            setFetching(true);
            load()
              .catch((e) => setLoadError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : onboarding ? (
        <div className="space-y-6">
          <Surface className="space-y-3 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={onboarding.status} />
              <span className="text-sm text-text-secondary">
                {progressLabel(onboarding)}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
              <div
                className="h-full rounded-full bg-teal transition-all"
                style={{ width: `${onboarding.progress_percent}%` }}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {WIZARD_STEPS.map((key) => {
                const meta = onboarding.steps.find((s) => s.key === key);
                return (
                  <button
                    key={key}
                    type="button"
                    className={`rounded-full border px-3 py-1 text-xs ${
                      activeStep === key
                        ? "border-teal bg-teal-soft text-teal"
                        : "border-border text-text-secondary"
                    }`}
                    onClick={() => setActiveStep(key)}
                  >
                    {meta?.title || key}
                  </button>
                );
              })}
            </div>
          </Surface>

          <Surface className="space-y-4 p-5">
            {activeStep === "business_profile" ? (
              <>
                <h2 className="text-sm font-semibold">Business profile</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Business name">
                    <Input
                      value={profile.business_name || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, business_name: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Business size">
                    <Select
                      value={profile.business_size || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, business_size: e.target.value })
                      }
                    >
                      <option value="">Select…</option>
                      {sizes.map((s) => (
                        <option key={s.key} value={s.key}>
                          {s.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Country">
                    <Input
                      value={profile.country || ""}
                      disabled={!canUpdate || closed}
                      placeholder="US"
                      onChange={(e) =>
                        setProfile({ ...profile, country: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="State">
                    <Input
                      value={profile.state || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, state: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Timezone">
                    <Input
                      value={profile.timezone || "UTC"}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, timezone: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Currency">
                    <Input
                      value={profile.currency || "USD"}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, currency: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Website">
                    <Input
                      value={profile.website || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, website: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Phone">
                    <Input
                      value={profile.phone || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, phone: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="Email">
                    <Input
                      value={profile.email || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        setProfile({ ...profile, email: e.target.value })
                      }
                    />
                  </Field>
                </div>
                {canUpdate && !closed ? (
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() => saveProfile(["business_profile"])}
                  >
                    Save & continue
                  </Button>
                ) : null}
              </>
            ) : null}

            {activeStep === "industry" ? (
              <>
                <h2 className="text-sm font-semibold">Industry</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {industries.map((ind) => (
                    <button
                      key={ind.key}
                      type="button"
                      disabled={!canUpdate || closed}
                      className={`rounded-lg border p-3 text-left ${
                        profile.industry === ind.key
                          ? "border-teal bg-teal-soft"
                          : "border-border"
                      }`}
                      onClick={() => setProfile({ ...profile, industry: ind.key })}
                    >
                      <div className="font-medium">{ind.name}</div>
                      <div className="text-xs text-text-secondary">
                        {ind.description}
                      </div>
                    </button>
                  ))}
                </div>
                {canUpdate && !closed ? (
                  <Button
                    type="button"
                    disabled={busy || !profile.industry}
                    onClick={() => saveProfile(["industry"])}
                  >
                    Save industry
                  </Button>
                ) : null}
              </>
            ) : null}

            {activeStep === "business_model" ? (
              <>
                <h2 className="text-sm font-semibold">Business model</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {models.map((m) => (
                    <button
                      key={m.key}
                      type="button"
                      disabled={!canUpdate || closed}
                      className={`rounded-lg border p-3 text-left ${
                        profile.business_type === m.key
                          ? "border-teal bg-teal-soft"
                          : "border-border"
                      }`}
                      onClick={() =>
                        setProfile({
                          ...profile,
                          business_type: m.key,
                          business_model: m.key,
                        })
                      }
                    >
                      <div className="font-medium">{m.name}</div>
                      <div className="text-xs text-text-secondary">
                        {m.description}
                      </div>
                    </button>
                  ))}
                </div>
                {canUpdate && !closed ? (
                  <Button
                    type="button"
                    disabled={busy || !profile.business_type}
                    onClick={() => void saveModel()}
                  >
                    Save business model
                  </Button>
                ) : null}
              </>
            ) : null}

            {activeStep === "catalog" ||
            activeStep === "customers" ||
            activeStep === "ai_configuration" ? (
              <>
                <h2 className="text-sm font-semibold">
                  {onboarding.steps.find((s) => s.key === activeStep)?.title}
                </h2>
                <p className="text-sm text-text-secondary">
                  Full domain setup ships in later phases. You can skip this
                  optional step or mark it complete to continue.
                </p>
                {canUpdate && !closed ? (
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      disabled={busy}
                      onClick={() => void completeOrSkip(activeStep)}
                    >
                      Mark complete
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={busy}
                      onClick={() => void completeOrSkip(activeStep, true)}
                    >
                      Skip
                    </Button>
                  </div>
                ) : null}
              </>
            ) : null}

            {activeStep === "business_hours" ? (
              <>
                <h2 className="text-sm font-semibold">Scheduling defaults</h2>
                <p className="text-sm text-text-secondary">
                  Timezone is taken from your business profile (
                  {profile.timezone || "UTC"}). Full scheduling configuration is
                  Phase 11.
                </p>
                {canUpdate && !closed ? (
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() => void completeOrSkip("business_hours")}
                  >
                    Use profile timezone & continue
                  </Button>
                ) : null}
              </>
            ) : null}

            {activeStep === "review" ? (
              <>
                <h2 className="text-sm font-semibold">Review</h2>
                <dl className="grid gap-2 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-text-muted">Business</dt>
                    <dd>{profile.business_name || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-text-muted">Industry</dt>
                    <dd>{profile.industry || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-text-muted">Business model</dt>
                    <dd>{profile.business_type || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-text-muted">Timezone</dt>
                    <dd>{profile.timezone || "—"}</dd>
                  </div>
                </dl>
                <div>
                  <h3 className="mb-2 text-sm font-medium">
                    Modules that will be enabled
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {(crm?.modules?.map((m) => m.key) || previewModules).map(
                      (key) => (
                        <StatusPill key={key} status={key} />
                      ),
                    )}
                  </div>
                </div>
                {crm?.setup_completed ? (
                  <p className="text-sm text-success">
                    CRM configuration already applied ({crm.template_key}).
                  </p>
                ) : (
                  <p className="text-sm text-text-secondary">
                    Completing onboarding will initialize CRM configuration
                    idempotently from the industry template.
                  </p>
                )}
                {canUpdate && !closed ? (
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() => void finishOnboarding()}
                  >
                    Complete onboarding
                  </Button>
                ) : null}
              </>
            ) : null}

            <div className="flex justify-between border-t border-border pt-4">
              <Button
                type="button"
                variant="secondary"
                disabled={stepIndex === 0}
                onClick={() => go(-1)}
              >
                Back
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={stepIndex >= WIZARD_STEPS.length - 1}
                onClick={() => go(1)}
              >
                Next
              </Button>
            </div>
          </Surface>
        </div>
      ) : null}
    </AppShell>
  );
}

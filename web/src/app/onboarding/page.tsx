"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { OnboardingChoice } from "@/components/onboarding/onboarding-choice";
import { OnboardingShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  isAiSetupConfirmed,
  isOnboardingComplete,
  isPhoneSetupReady,
  needsPhoneSetup,
  ONBOARDING_AI_PATH,
  PHONES_ONBOARDING_PATH,
  progressLabel,
  resumeTarget,
  SETUP_PATH_KEY,
  setupPathFromState,
  type OnboardingSetupPath,
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
  PhoneE164Input,
  Select,
  StatusPill,
  Surface,
  useToast,
} from "@/components/ui";
import { fetchOrgGeoRegions } from "@/lib/geo-api";
import {
  applyLiveGeoDefaults,
  catalogToCountryOptions,
  catalogToCurrencyOptions,
  catalogToOptions,
  defaultCurrencyForCountry,
  normalizeCountryCode,
  normalizeCurrencyCode,
  optionsWithCurrent,
  type CountryCatalogItem,
  type GeoOption,
} from "@/lib/geo-options";
import { timezoneOptionsForSelect } from "@/lib/timezones";

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

class OnboardingApiError extends Error {
  code?: string;
  constructor(message: string, code?: string) {
    super(message);
    this.code = code;
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let message = errors.saveFailed;
    let code: string | undefined;
    try {
      const body = await res.json();
      message = body?.detail?.message || body?.detail || message;
      if (typeof body?.detail === "object" && body?.detail?.code) {
        code = String(body.detail.code);
      }
    } catch {
      /* ignore */
    }
    throw new OnboardingApiError(
      typeof message === "string" ? message : errors.saveFailed,
      code,
    );
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
  "phone_setup",
  "review",
] as const;

export default function OnboardingPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <OnboardingPageInner />
    </Suspense>
  );
}

function OnboardingPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const forceManual = searchParams.get("manual") === "1";
  const { user, loading, forbidden, refresh } = useAuth({
    permission: "organization.read",
    allowIncompleteOnboarding: true,
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
  const [countries, setCountries] = useState<GeoOption[]>([]);
  const [countryCatalog, setCountryCatalog] = useState<CountryCatalogItem[]>(
    [],
  );
  const [currencies, setCurrencies] = useState<GeoOption[]>([]);
  const [timezones, setTimezones] = useState<GeoOption[]>([]);
  const [regions, setRegions] = useState<GeoOption[]>([]);
  const [regionsLoading, setRegionsLoading] = useState(false);
  const [crm, setCrm] = useState<CrmConfiguration>(null);
  const [previewModules, setPreviewModules] = useState<string[]>([]);
  const [activeStep, setActiveStep] = useState<string>("business_profile");
  const [fetching, setFetching] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pathBusy, setPathBusy] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const leftCompletedRef = useRef(false);
  const profileRef = useRef<BusinessProfile>({});
  const lastSavedProfileRef = useRef<string>("");
  const profileSaveInFlightRef = useRef(false);

  function profileSnapshot(p: BusinessProfile): string {
    return JSON.stringify({
      business_name: p.business_name || null,
      industry: p.industry || null,
      country: normalizeCountryCode(p.country) || p.country || null,
      state: p.state || null,
      timezone: p.timezone || "UTC",
      currency: normalizeCurrencyCode(p.currency) || p.currency || "USD",
      website: p.website || null,
      phone: p.phone || null,
      email: p.email || null,
      business_size: p.business_size || null,
      business_type: p.business_type || null,
    });
  }

  const load = useCallback(async () => {
    const [ob, bp, cfg] = await Promise.all([
      api<{ onboarding: OnboardingState }>("/api/admin/organization/onboarding"),
      api<{
        profile: BusinessProfile;
        catalogs: {
          industries: CatalogOption[];
          business_models: CatalogOption[];
          business_sizes: CatalogOption[];
          countries?: CountryCatalogItem[];
          currencies?: Array<{
            key: string;
            name: string;
            symbol?: string | null;
          }>;
          timezones?: CatalogOption[];
        };
      }>("/api/admin/organization/business-profile"),
      api<{
        configuration: CrmConfiguration;
        preview_template: { modules: string[] };
      }>("/api/admin/organization/crm-configuration"),
    ]);
    setOnboarding(ob.onboarding);
    const rawProfile = bp.profile || {};
    const countryRows = bp.catalogs.countries || [];
    const normalizedRaw = {
      ...rawProfile,
      country: normalizeCountryCode(rawProfile.country) || rawProfile.country,
      currency:
        normalizeCurrencyCode(rawProfile.currency) || rawProfile.currency,
      timezone: rawProfile.timezone || null,
    };
    // Saved country must never be rewritten by browser locale/timezone on refresh.
    const hasSavedCountry = Boolean(
      normalizeCountryCode(normalizedRaw.country),
    );
    const withLive = hasSavedCountry
      ? {
          ...normalizedRaw,
          currency: normalizeCurrencyCode(normalizedRaw.currency) || "USD",
          timezone: (normalizedRaw.timezone || "").trim() || "UTC",
        }
      : applyLiveGeoDefaults(normalizedRaw, countryRows);
    const loadedProfile = {
      ...withLive,
      currency: normalizeCurrencyCode(withLive.currency) || "USD",
      timezone: withLive.timezone || "UTC",
    };
    setProfile(loadedProfile);
    profileRef.current = loadedProfile;
    lastSavedProfileRef.current = profileSnapshot(loadedProfile);
    setIndustries(bp.catalogs.industries || []);
    setModels(bp.catalogs.business_models || []);
    setSizes(bp.catalogs.business_sizes || []);
    setCountryCatalog(countryRows);
    setCountries(catalogToCountryOptions(countryRows));
    setCurrencies(catalogToCurrencyOptions(bp.catalogs.currencies));
    setTimezones(catalogToOptions(bp.catalogs.timezones));
    setCrm(cfg.configuration);
    setPreviewModules(cfg.preview_template?.modules || []);
    const resume = resumeTarget(ob.onboarding);
    setActiveStep(resume || "business_profile");
    setLoadError(null);
    return ob.onboarding;
  }, []);

  useEffect(() => {
    if (!user) return;
    load()
      .catch((e) => setLoadError(safeUserError(e, errors.loadFailed)))
      .finally(() => setFetching(false));
  }, [user, load]);

  const businessClosed = onboarding?.status === "COMPLETED";
  /** Wizard mutations closed; phone recovery still allowed via /phones. */
  const closed = businessClosed;
  const phoneReady = isPhoneSetupReady(onboarding) || user?.phone_ready === true;
  const phoneRecovery = Boolean(businessClosed && !phoneReady);
  const setupPath = setupPathFromState(onboarding);
  const aiConfirmed = isAiSetupConfirmed(onboarding);
  const showChoice = Boolean(
    onboarding && !closed && !setupPath && !forceManual,
  );

  // Full app access only when business + phone are ready (server-aligned).
  useEffect(() => {
    if (loading || fetching || !onboarding || !user) return;
    if (leftCompletedRef.current) return;
    if (isOnboardingComplete(user) && phoneReady) {
      leftCompletedRef.current = true;
      router.replace("/dashboard");
      return;
    }
    if (needsPhoneSetup(user) || phoneRecovery) {
      setActiveStep("phone_setup");
    }
  }, [
    loading,
    fetching,
    onboarding,
    user,
    phoneReady,
    phoneRecovery,
    router,
  ]);

  // Resume AI path when draft not yet confirmed.
  useEffect(() => {
    if (fetching || !onboarding || closed || forceManual) return;
    if (setupPath === "ai" && !aiConfirmed) {
      router.replace(ONBOARDING_AI_PATH);
    }
  }, [
    fetching,
    onboarding,
    closed,
    forceManual,
    setupPath,
    aiConfirmed,
    router,
  ]);

  async function persistSetupPath(path: OnboardingSetupPath) {
    const data = await api<{ onboarding: OnboardingState }>(
      "/api/admin/organization/onboarding",
      {
        method: "PATCH",
        body: JSON.stringify({
          state_data: { [SETUP_PATH_KEY]: path },
          current_step: path === "manual" ? "business_profile" : "ai_configuration",
        }),
      },
    );
    setOnboarding(data.onboarding);
    return data.onboarding;
  }

  async function chooseAi() {
    if (!canUpdate) return;
    setPathBusy(true);
    try {
      await persistSetupPath("ai");
      router.push(ONBOARDING_AI_PATH);
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setPathBusy(false);
    }
  }

  async function chooseManual() {
    if (!canUpdate) return;
    setPathBusy(true);
    try {
      await persistSetupPath("manual");
      setActiveStep("business_profile");
      // Path is already "manual" — no query flag needed for resume.
      router.replace("/onboarding");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setPathBusy(false);
    }
  }

  async function changeSetupMethod() {
    if (!canUpdate || !onboarding) return;
    setPathBusy(true);
    try {
      const data = await api<{ onboarding: OnboardingState }>(
        "/api/admin/organization/onboarding",
        {
          method: "PATCH",
          body: JSON.stringify({ state_data: { [SETUP_PATH_KEY]: null } }),
        },
      );
      setOnboarding(data.onboarding);
      router.replace("/onboarding");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setPathBusy(false);
    }
  }

  const stepIndex = useMemo(
    () => Math.max(0, WIZARD_STEPS.indexOf(activeStep as (typeof WIZARD_STEPS)[number])),
    [activeStep],
  );

  const countryOptions = useMemo(
    () => optionsWithCurrent(countries, profile.country),
    [countries, profile.country],
  );
  const regionOptions = useMemo(
    () => optionsWithCurrent(regions, profile.state),
    [regions, profile.state],
  );
  const timezoneOptions = useMemo(
    () =>
      timezoneOptionsForSelect(
        profile.timezone || "UTC",
        timezones.map((t) => ({ value: t.value, label: t.label })),
      ),
    [profile.timezone, timezones],
  );
  const currencyOptions = useMemo(
    () => optionsWithCurrent(currencies, profile.currency),
    [currencies, profile.currency],
  );

  useEffect(() => {
    const code = normalizeCountryCode(profile.country);
    if (!code) {
      setRegions([]);
      setRegionsLoading(false);
      return;
    }
    const controller = new AbortController();
    setRegionsLoading(true);
    fetchOrgGeoRegions(code, { signal: controller.signal })
      .then((result) => {
        setRegions(catalogToOptions(result.regions));
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setRegions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setRegionsLoading(false);
      });
    return () => controller.abort();
  }, [profile.country]);

  function updateProfile(patch: Partial<BusinessProfile>) {
    const next = { ...profileRef.current, ...patch };
    profileRef.current = next;
    setProfile(next);
  }

  function applyServerProfile(server: BusinessProfile) {
    const next = {
      ...profileRef.current,
      ...server,
      // Keep optimistic selection if server omits a just-picked value.
      industry: server.industry ?? profileRef.current.industry,
      business_type: server.business_type ?? profileRef.current.business_type,
      business_model:
        server.business_model ??
        server.business_type ??
        profileRef.current.business_model,
    };
    profileRef.current = next;
    lastSavedProfileRef.current = profileSnapshot(next);
    setProfile(next);
  }

  async function autosaveBusinessProfile(opts?: { quiet?: boolean }) {
    if (!canUpdate || closed) return;
    const current = profileRef.current;
    const snapshot = profileSnapshot(current);
    if (snapshot === lastSavedProfileRef.current) return;
    if (profileSaveInFlightRef.current) return;
    profileSaveInFlightRef.current = true;
    setProfileSaving(true);
    try {
      const country = normalizeCountryCode(current.country) || null;
      const currency =
        normalizeCurrencyCode(current.currency) || current.currency || "USD";
      const data = await api<{
        profile: BusinessProfile;
        onboarding?: OnboardingState;
      }>("/api/admin/organization/business-profile", {
        method: "PATCH",
        body: JSON.stringify({
          business_name: current.business_name || null,
          industry: current.industry || null,
          country,
          state: current.state || null,
          timezone: current.timezone || "UTC",
          currency,
          website: current.website || null,
          phone: current.phone || null,
          email: current.email || null,
          business_size: current.business_size || null,
          business_type: current.business_type || null,
          complete_steps: ["business_profile"],
        }),
      });
      applyServerProfile(data.profile);
      if (data.onboarding) setOnboarding(data.onboarding);
      if (!opts?.quiet) toast.push("Saved", "success");
      await refreshCrm();
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      profileSaveInFlightRef.current = false;
      setProfileSaving(false);
    }
  }

  async function saveIndustry(industryKey: string, opts?: { quiet?: boolean }) {
    const key = industryKey.trim();
    if (!canUpdate || !key) return;
    updateProfile({ industry: key });
    setBusy(true);
    try {
      // Only patch industry — avoid failing the whole save on unrelated geo/phone.
      const data = await api<{
        profile: BusinessProfile;
        onboarding?: OnboardingState;
      }>("/api/admin/organization/business-profile", {
        method: "PATCH",
        body: JSON.stringify({
          industry: key,
          complete_steps: ["industry"],
        }),
      });
      applyServerProfile(data.profile);
      if (data.onboarding) setOnboarding(data.onboarding);
      if (!opts?.quiet) toast.push("Saved", "success");
      await refreshCrm();
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function saveModel(modelKey?: string, opts?: { quiet?: boolean }) {
    const key = (modelKey || profileRef.current.business_type || "").trim();
    if (!canUpdate || !key) return;
    updateProfile({ business_type: key, business_model: key });
    setBusy(true);
    try {
      const data = await api<{
        business_model: string;
        onboarding: OnboardingState;
      }>("/api/admin/organization/business-model", {
        method: "PUT",
        body: JSON.stringify({ business_model: key }),
      });
      applyServerProfile({
        ...profileRef.current,
        business_type: data.business_model,
        business_model: data.business_model,
      });
      setOnboarding(data.onboarding);
      if (!opts?.quiet) toast.push("Business model saved", "success");
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
      await refresh();
      toast.push("Onboarding completed", "success");
      router.replace("/dashboard");
    } catch (e) {
      const message = safeUserError(e, errors.saveFailed);
      toast.push(message, "error");
      const code =
        e && typeof e === "object" && "code" in e
          ? String((e as { code?: string }).code || "")
          : "";
      if (
        code === "phone_required" ||
        code === "phone_pending" ||
        code === "phone_ineligible"
      ) {
        setActiveStep("phone_setup");
        await load().catch(() => undefined);
      }
    } finally {
      setBusy(false);
    }
  }

  // Poll phone readiness while on the phone step (provisioning/verification).
  useEffect(() => {
    if (activeStep !== "phone_setup" || closed || !user) return;
    if (isPhoneSetupReady(onboarding)) return;
    const id = window.setInterval(() => {
      void load().catch(() => undefined);
    }, 8000);
    return () => window.clearInterval(id);
  }, [activeStep, closed, user, onboarding, load]);

  async function refreshCrm() {
    const cfg = await api<{
      configuration: CrmConfiguration;
      preview_template: { modules: string[] };
    }>("/api/admin/organization/crm-configuration");
    setCrm(cfg.configuration);
    setPreviewModules(cfg.preview_template?.modules || []);
  }

  async function go(delta: number) {
    if (
      delta > 0 &&
      activeStep === "business_profile" &&
      canUpdate &&
      !closed
    ) {
      await autosaveBusinessProfile({ quiet: true });
    }
    const next = WIZARD_STEPS[stepIndex + delta];
    if (next) setActiveStep(next);
  }

  if (loading || !user || fetching) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }
  if (forbidden) {
    return (
      <OnboardingShell user={user}>
        <ForbiddenState />
      </OnboardingShell>
    );
  }
  if (loadError) {
    return (
      <OnboardingShell user={user}>
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
      </OnboardingShell>
    );
  }

  if (showChoice) {
    return (
      <OnboardingShell user={user}>
        <OnboardingChoice
          busy={pathBusy || !canUpdate}
          onChooseAi={() => void chooseAi()}
          onChooseManual={() => void chooseManual()}
        />
      </OnboardingShell>
    );
  }

  // Avoid flashing the manual wizard while redirecting into AI setup.
  if (
    onboarding &&
    !closed &&
    setupPath === "ai" &&
    !aiConfirmed &&
    !forceManual
  ) {
    return (
      <OnboardingShell user={user}>
        <LoadingSkeleton rows={6} />
      </OnboardingShell>
    );
  }

  return (
    <OnboardingShell user={user}>
      <PageHeader
        title="Business onboarding"
        description="Configure your organization profile, industry, business model, and CRM modules. Required steps must be completed before using the dashboard."
      />

      {onboarding ? (
        <div className="space-y-6">
          <Surface className="space-y-3 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <StatusPill status={onboarding.status} />
                <span className="text-sm text-text-secondary">
                  {progressLabel(onboarding)}
                </span>
                {setupPath ? (
                  <span className="text-xs text-text-muted uppercase tracking-wide">
                    {setupPath === "ai" ? "AI setup" : "Manual setup"}
                  </span>
                ) : null}
              </div>
              {canUpdate && !closed ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={pathBusy}
                  onClick={() => void changeSetupMethod()}
                >
                  Change setup method
                </Button>
              ) : null}
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
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold">Business profile</h2>
                  {profileSaving ? (
                    <span className="text-xs text-text-muted">Saving…</span>
                  ) : null}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Business name">
                    <Input
                      value={profile.business_name || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        updateProfile({ business_name: e.target.value })
                      }
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    />
                  </Field>
                  <Field label="Business size">
                    <Select
                      value={profile.business_size || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) => {
                        updateProfile({ business_size: e.target.value });
                        void autosaveBusinessProfile({ quiet: true });
                      }}
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
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
                    <Select
                      value={normalizeCountryCode(profile.country) || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) => {
                        const nextCountry = e.target.value;
                        const nextCurrency =
                          defaultCurrencyForCountry(
                            nextCountry,
                            countryCatalog,
                          ) || profile.currency;
                        updateProfile({
                          country: nextCountry,
                          state: "",
                          currency: nextCurrency,
                        });
                        void autosaveBusinessProfile({ quiet: true });
                      }}
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    >
                      <option value="">Select…</option>
                      {countryOptions.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="State / Province">
                    {regionsLoading || regions.length > 0 ? (
                      <Select
                        value={profile.state || ""}
                        disabled={
                          !canUpdate ||
                          closed ||
                          regionsLoading ||
                          !profile.country
                        }
                        onChange={(e) => {
                          updateProfile({ state: e.target.value });
                          void autosaveBusinessProfile({ quiet: true });
                        }}
                        onBlur={() =>
                          void autosaveBusinessProfile({ quiet: true })
                        }
                      >
                        <option value="">
                          {regionsLoading ? "Loading…" : "Select…"}
                        </option>
                        {regionOptions.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <Input
                        value={profile.state || ""}
                        disabled={!canUpdate || closed || !profile.country}
                        placeholder={
                          profile.country
                            ? "State / province"
                            : "Select a country first"
                        }
                        onChange={(e) =>
                          updateProfile({ state: e.target.value })
                        }
                        onBlur={() =>
                          void autosaveBusinessProfile({ quiet: true })
                        }
                      />
                    )}
                  </Field>
                  <Field label="Timezone">
                    <Select
                      value={profile.timezone || "UTC"}
                      disabled={!canUpdate || closed}
                      onChange={(e) => {
                        updateProfile({ timezone: e.target.value });
                        void autosaveBusinessProfile({ quiet: true });
                      }}
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    >
                      {timezoneOptions.map((tz) => (
                        <option key={tz.value} value={tz.value}>
                          {tz.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Currency">
                    <Select
                      value={
                        normalizeCurrencyCode(profile.currency) || "USD"
                      }
                      disabled={!canUpdate || closed}
                      onChange={(e) => {
                        updateProfile({ currency: e.target.value });
                        void autosaveBusinessProfile({ quiet: true });
                      }}
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    >
                      {currencyOptions.map((c) => (
                        <option key={c.value} value={c.value}>
                          {c.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Website">
                    <Input
                      value={profile.website || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        updateProfile({ website: e.target.value })
                      }
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    />
                  </Field>
                  <Field label="Phone" className="sm:col-span-2">
                    <PhoneE164Input
                      value={profile.phone || ""}
                      countryIso={profile.country}
                      disabled={!canUpdate || closed}
                      onChange={(e164) => updateProfile({ phone: e164 })}
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    />
                  </Field>
                  <Field label="Email" className="sm:col-span-2">
                    <Input
                      value={profile.email || ""}
                      disabled={!canUpdate || closed}
                      onChange={(e) =>
                        updateProfile({ email: e.target.value })
                      }
                      onBlur={() =>
                        void autosaveBusinessProfile({ quiet: true })
                      }
                    />
                  </Field>
                </div>
              </>
            ) : null}

            {activeStep === "industry" ? (
              <>
                <h2 className="text-sm font-semibold">Industry</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {industries.map((ind) => {
                    const selected = profile.industry === ind.key;
                    return (
                      <button
                        key={ind.key}
                        type="button"
                        disabled={!canUpdate || closed || busy}
                        aria-pressed={selected}
                        className={`rounded-lg border p-3 text-left transition-colors ${
                          selected
                            ? "border-teal bg-teal-soft font-semibold text-teal-deep shadow-[var(--shadow-sm)]"
                            : "border-border hover:border-teal/40"
                        }`}
                        onClick={() =>
                          void saveIndustry(ind.key, { quiet: true })
                        }
                      >
                        <div className="font-medium">{ind.name}</div>
                        <div className="text-xs font-normal text-text-secondary">
                          {ind.description}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </>
            ) : null}

            {activeStep === "business_model" ? (
              <>
                <h2 className="text-sm font-semibold">Business model</h2>
                <div className="grid gap-2 sm:grid-cols-2">
                  {models.map((m) => {
                    const selected = profile.business_type === m.key;
                    return (
                      <button
                        key={m.key}
                        type="button"
                        disabled={!canUpdate || closed || busy}
                        aria-pressed={selected}
                        className={`rounded-lg border p-3 text-left transition-colors ${
                          selected
                            ? "border-teal bg-teal-soft font-semibold text-teal-deep shadow-[var(--shadow-sm)]"
                            : "border-border hover:border-teal/40"
                        }`}
                        onClick={() => void saveModel(m.key, { quiet: true })}
                      >
                        <div className="font-medium">{m.name}</div>
                        <div className="text-xs font-normal text-text-secondary">
                          {m.description}
                        </div>
                      </button>
                    );
                  })}
                </div>
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

            {activeStep === "phone_setup" ? (
              <>
                <h2 className="text-sm font-semibold">
                  Configure Your Business Phone Number
                </h2>
                <p className="text-sm text-text-secondary">
                  Every organization — including existing customers — must have
                  at least one verified inbound phone number before accessing
                  the dashboard. Choose how you want to set it up:
                </p>
                <ul className="list-disc space-y-1 pl-5 text-sm text-text-secondary">
                  <li>
                    <strong className="text-text-primary">
                      I already have a number
                    </strong>{" "}
                    — connect a supported Twilio number and complete inbound
                    verification (BYON).
                  </li>
                  <li>
                    <strong className="text-text-primary">
                      Purchase a new number
                    </strong>{" "}
                    — search inventory, confirm price, then buy (charges only
                    after you confirm).
                  </li>
                </ul>
                <div className="rounded-lg border border-border bg-surface-muted/40 p-4 text-sm">
                  <p className="font-medium text-text-primary">
                    Status:{" "}
                    {onboarding.phone_setup?.state === "ready"
                      ? "Ready"
                      : onboarding.phone_setup?.state === "setup_in_progress"
                        ? "Setup in progress"
                        : onboarding.phone_setup?.state === "action_required"
                          ? "Action required"
                          : "Not configured"}
                  </p>
                  {onboarding.phone_setup?.primary_e164 ? (
                    <p className="mt-1 text-text-secondary">
                      Number: {onboarding.phone_setup.primary_e164}
                    </p>
                  ) : null}
                  {onboarding.phone_setup?.message ? (
                    <p className="mt-2 text-text-secondary">
                      {onboarding.phone_setup.message}
                    </p>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => router.push(PHONES_ONBOARDING_PATH)}
                  >
                    Open phone setup
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => {
                      void load();
                      void refresh();
                    }}
                  >
                    Refresh status
                  </Button>
                  {canUpdate && !closed ? (
                    <Button
                      type="button"
                      disabled={busy || !isPhoneSetupReady(onboarding)}
                      onClick={() => void completeOrSkip("phone_setup")}
                    >
                      {isPhoneSetupReady(onboarding)
                        ? "Continue"
                        : "Waiting for a ready number…"}
                    </Button>
                  ) : null}
                  {phoneRecovery && phoneReady ? (
                    <Button
                      type="button"
                      onClick={() => {
                        void refresh().then((u) => {
                          if (u && isOnboardingComplete(u)) {
                            router.replace("/dashboard");
                          }
                        });
                      }}
                    >
                      Continue to dashboard
                    </Button>
                  ) : null}
                </div>
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
                  <div>
                    <dt className="text-text-muted">Phone number</dt>
                    <dd>
                      {onboarding.phone_setup?.primary_e164 ||
                        (isPhoneSetupReady(onboarding)
                          ? "Ready"
                          : "Required — not ready")}
                    </dd>
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
              </>
            ) : null}

            <div className="flex flex-col gap-2 border-t border-border pt-4">
              <div className="flex justify-between gap-3">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={stepIndex === 0 || busy || profileSaving}
                  onClick={() => void go(-1)}
                >
                  Back
                </Button>
                {activeStep === "review" ? (
                  closed ? (
                    <Button
                      type="button"
                      onClick={() => router.replace("/dashboard")}
                    >
                      Go to dashboard
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      disabled={busy || !canUpdate}
                      onClick={() => void finishOnboarding()}
                    >
                      {busy ? "Finishing…" : "Finish"}
                    </Button>
                  )
                ) : (
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={
                      stepIndex >= WIZARD_STEPS.length - 1 ||
                      busy ||
                      profileSaving
                    }
                    onClick={() => void go(1)}
                  >
                    Next
                  </Button>
                )}
              </div>
              {activeStep === "review" && !closed && !canUpdate ? (
                <p className="text-sm text-danger">
                  Finish needs the organization.update permission. Ask an Owner
                  or Admin to complete onboarding, or re-login after roles are
                  assigned.
                </p>
              ) : null}
              {activeStep === "review" &&
              !closed &&
              canUpdate &&
              (onboarding.required_remaining?.length ?? 0) > 0 ? (
                <p className="text-sm text-text-secondary">
                  Still required: {onboarding.required_remaining.join(", ")}.
                  Finish will validate these on the server.
                </p>
              ) : null}
            </div>
          </Surface>
        </div>
      ) : null}
    </OnboardingShell>
  );
}

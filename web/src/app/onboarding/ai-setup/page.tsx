"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bot,
  Check,
  Loader2,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { OnboardingShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { hasPermission } from "@/lib/permissions";
import { ONBOARDING_PATH, SETUP_PATH_KEY } from "@/lib/onboarding";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  analyzeBusiness,
  confirmBusinessSetup,
  confidenceLabel,
  getBusinessSetup,
  saveRecommendationDraft,
  type BusinessSetupState,
  type CustomFieldRec,
  type ModuleRec,
  type ProductCategoryRec,
  type ServiceRec,
  type SetupRecommendation,
} from "@/lib/api/business-setup";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
} from "@/components/ui";

type Step =
  | "describe"
  | "analyzing"
  | "clarify"
  | "review"
  | "confirming"
  | "done";

const ANALYZE_STAGES = [
  "Understanding your business",
  "Identifying your industry",
  "Building your recommended workspace",
  "Preparing your AI setup",
] as const;

function cloneRec(rec: SetupRecommendation): SetupRecommendation {
  return structuredClone(rec);
}

function humanizeKey(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

type FlowStage = "describe" | "generate" | "review" | "done";

function flowStage(step: Step): FlowStage {
  if (step === "done") return "done";
  if (step === "review" || step === "confirming") return "review";
  if (step === "analyzing" || step === "clarify") return "generate";
  return "describe";
}

const FLOW_STAGES: { id: FlowStage; label: string }[] = [
  { id: "describe", label: "Describe" },
  { id: "generate", label: "Generate" },
  { id: "review", label: "Review" },
  { id: "done", label: "Save" },
];

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export default function AiBusinessSetupPage() {
  const router = useRouter();
  const { user, loading, forbidden, refresh } = useAuth({
    permission: "business_setup.read",
    allowIncompleteOnboarding: true,
  });
  const toast = useToast();
  const canGenerate = hasPermission(user, "business_setup.generate");
  const canUpdate = hasPermission(user, "business_setup.update");
  const canConfirm = hasPermission(user, "business_setup.confirm");
  const canOrgUpdate = hasPermission(user, "organization.update");

  const [setup, setSetup] = useState<BusinessSetupState | null>(null);
  const [description, setDescription] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<SetupRecommendation | null>(null);
  const [step, setStep] = useState<Step>("describe");
  const [fetching, setFetching] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [analyzeStage, setAnalyzeStage] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmResult, setConfirmResult] = useState<Record<
    string,
    unknown
  > | null>(null);

  const load = useCallback(async () => {
    setFetching(true);
    setLoadError(null);
    try {
      const res = await getBusinessSetup();
      setSetup(res.setup);
      if (res.setup.description) setDescription(res.setup.description);
      if (res.setup.recommendation) {
        setDraft(cloneRec(res.setup.recommendation));
        if (res.setup.status === "CONFIRMED") {
          setStep("done");
          setConfirmResult(res.setup.last_confirm_result || null);
        } else if (res.setup.status === "CLARIFY") {
          setStep("clarify");
        } else if (res.setup.status === "REVIEW") {
          setStep("review");
        }
      }
    } catch (err) {
      setLoadError(safeUserError(err, errors.loadFailed));
    } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Ensure setup_path is persisted when landing here from bookmarks/deep links.
  useEffect(() => {
    if (!user || !canOrgUpdate) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch(`${API}/api/admin/organization/onboarding`, {
          credentials: "include",
        });
        if (!res.ok || cancelled) return;
        const body = (await res.json()) as {
          onboarding?: { state_data?: Record<string, unknown>; status?: string };
        };
        const status = body.onboarding?.status;
        if (status === "COMPLETED") return;
        if (body.onboarding?.state_data?.[SETUP_PATH_KEY] === "ai") return;
        await fetch(`${API}/api/admin/organization/onboarding`, {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            state_data: { [SETUP_PATH_KEY]: "ai" },
            current_step: "ai_configuration",
          }),
        });
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, canOrgUpdate]);

  useEffect(() => {
    if (step !== "analyzing") return;
    setAnalyzeStage(0);
    const id = window.setInterval(() => {
      setAnalyzeStage((s) => Math.min(s + 1, ANALYZE_STAGES.length - 1));
    }, 900);
    return () => window.clearInterval(id);
  }, [step]);

  const industryLabel = useMemo(() => {
    const ind = draft?.business_profile.industry;
    if (!ind) return "—";
    return ind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }, [draft]);

  async function onAnalyze() {
    if (!canGenerate || description.trim().length < 8) return;
    setBusy(true);
    setStep("analyzing");
    try {
      const res = await analyzeBusiness(description.trim(), answers);
      setSetup(res.setup);
      if (res.setup.recommendation) {
        setDraft(cloneRec(res.setup.recommendation));
      }
      if (res.setup.status === "CLARIFY") {
        setStep("clarify");
      } else {
        setStep("review");
      }
    } catch (err) {
      toast.push(
        safeUserError(
          err,
          "We couldn't analyze your business right now. Please try again.",
        ),
        "error",
      );
      setStep("describe");
    } finally {
      setBusy(false);
    }
  }

  async function onClarifyContinue() {
    if (!canGenerate) return;
    setBusy(true);
    setStep("analyzing");
    try {
      const res = await analyzeBusiness(description.trim(), answers);
      setSetup(res.setup);
      if (res.setup.recommendation) {
        setDraft(cloneRec(res.setup.recommendation));
      }
      setStep("review");
    } catch (err) {
      toast.push(
        safeUserError(
          err,
          "We couldn't analyze your business right now. Please try again.",
        ),
        "error",
      );
      setStep("clarify");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveDraft() {
    if (!draft || !canUpdate) return;
    setBusy(true);
    try {
      const res = await saveRecommendationDraft(draft);
      setSetup(res.setup);
      if (res.setup.recommendation) setDraft(cloneRec(res.setup.recommendation));
      toast.push("Draft saved", "success");
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!draft || !setup?.operation_id || !canConfirm) return;
    setConfirmOpen(false);
    setBusy(true);
    setStep("confirming");
    try {
      const res = await confirmBusinessSetup({
        operation_id: setup.operation_id,
        recommendation: draft,
      });
      setConfirmResult(res.result);
      setStep("done");
      toast.push(
        res.idempotent
          ? "Setup already confirmed"
          : "Business setup confirmed",
        "success",
      );
      await load();
      await refresh();
      if (res.result?.onboarding_complete === true) {
        router.replace("/dashboard");
        return;
      }
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
      setStep("review");
    } finally {
      setBusy(false);
    }
  }

  function toggleModule(key: string) {
    if (!draft) return;
    setDraft({
      ...draft,
      modules: draft.modules.map((m) =>
        m.key === key ? { ...m, selected: !m.selected } : m,
      ),
    });
  }

  function removeService(idx: number) {
    if (!draft) return;
    setDraft({
      ...draft,
      services: draft.services.filter((_, i) => i !== idx),
    });
  }

  function addService() {
    if (!draft) return;
    const name = window.prompt("Service name");
    if (!name?.trim()) return;
    const next: ServiceRec = {
      name: name.trim(),
      description: null,
      reason: "Added by owner",
      selected: true,
      price: null,
    };
    setDraft({ ...draft, services: [...draft.services, next] });
  }

  function removeField(idx: number) {
    if (!draft) return;
    setDraft({
      ...draft,
      custom_fields: draft.custom_fields.filter((_, i) => i !== idx),
    });
  }

  function addField() {
    if (!draft) return;
    const name = window.prompt("Custom field label");
    if (!name?.trim()) return;
    const entity = window.prompt("CRM module key (e.g. CUSTOMERS, EQUIPMENT)", "CUSTOMERS");
    if (!entity?.trim()) return;
    const field_key = name
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_")
      .replace(/[^a-z0-9_]/g, "")
      .slice(0, 64);
    const next: CustomFieldRec = {
      name: name.trim(),
      field_key: field_key || "custom_field",
      entity: entity.trim().toUpperCase(),
      reason: "Added by owner",
      selected: true,
    };
    setDraft({ ...draft, custom_fields: [...draft.custom_fields, next] });
  }

  function removeProduct(idx: number) {
    if (!draft) return;
    setDraft({
      ...draft,
      product_categories: draft.product_categories.filter((_, i) => i !== idx),
    });
  }

  function resetFlow() {
    setAnswers({});
    setDraft(null);
    setConfirmResult(null);
    setStep("describe");
  }

  const stage = flowStage(step);
  const stageIndex = FLOW_STAGES.findIndex((s) => s.id === stage);
  const descriptionLen = description.trim().length;
  const canGenerateNow = canGenerate && descriptionLen >= 8 && !busy;

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }
  if (fetching) {
    return (
      <OnboardingShell user={user}>
        <LoadingSkeleton rows={6} />
      </OnboardingShell>
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
        <ErrorState message={loadError} onRetry={() => void load()} />
      </OnboardingShell>
    );
  }

  return (
    <OnboardingShell user={user}>
      <div className="mx-auto w-full max-w-3xl space-y-6">
      <div className="space-y-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="-ml-2"
          onClick={() => {
            void (async () => {
              if (canOrgUpdate) {
                try {
                  await fetch(`${API}/api/admin/organization/onboarding`, {
                    method: "PATCH",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      state_data: { [SETUP_PATH_KEY]: null },
                    }),
                  });
                } catch {
                  /* still navigate */
                }
              }
              router.push(ONBOARDING_PATH);
            })();
          }}
        >
          ← Back to setup options
        </Button>
        <PageHeader
          title="Set up with AI"
          description="Describe your business. We’ll draft industry, modules, services, and AI calling settings — nothing is saved until you confirm."
        />
      </div>

      <nav aria-label="AI setup progress" className="space-y-3">
        <ol className="flex flex-wrap gap-2">
          {FLOW_STAGES.map((item, index) => {
            const done = index < stageIndex;
            const active = index === stageIndex;
            const canJump =
              !busy &&
              ((item.id === "describe" &&
                (step === "review" ||
                  step === "clarify" ||
                  step === "done" ||
                  step === "describe")) ||
                (item.id === "review" &&
                  Boolean(draft) &&
                  step !== "analyzing" &&
                  step !== "confirming") ||
                (item.id === "done" && step === "done"));
            const className = `inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              active
                ? "border-teal bg-teal-soft text-teal-deep"
                : done
                  ? "border-teal/40 bg-teal-soft/50 text-teal"
                  : "border-border bg-surface text-text-muted"
            } ${canJump && !active ? "cursor-pointer hover:border-teal/50" : ""}`;
            const content = (
              <>
                {done ? (
                  <Check className="size-3.5 shrink-0" strokeWidth={2.5} aria-hidden />
                ) : (
                  <span
                    className={`inline-flex size-4 shrink-0 items-center justify-center rounded-full text-[10px] ${
                      active ? "bg-teal text-white" : "bg-surface-muted"
                    }`}
                    aria-hidden
                  >
                    {index + 1}
                  </span>
                )}
                {item.label}
              </>
            );
            if (!canJump || active) {
              return (
                <li key={item.id}>
                  <span
                    className={className}
                    aria-current={active ? "step" : undefined}
                  >
                    {content}
                  </span>
                </li>
              );
            }
            return (
              <li key={item.id}>
                <button
                  type="button"
                  className={className}
                  onClick={() => {
                    if (item.id === "describe") setStep("describe");
                    else if (item.id === "review" && draft) setStep("review");
                  }}
                >
                  {content}
                </button>
              </li>
            );
          })}
        </ol>
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-muted">
          <div
            className="h-full rounded-full bg-teal transition-all duration-300"
            style={{
              width: `${Math.round(((stageIndex + 1) / FLOW_STAGES.length) * 100)}%`,
            }}
          />
        </div>
      </nav>

      {(step === "describe" || step === "analyzing") && (
        <Surface className="space-y-5 p-6">
          <div className="flex items-start gap-3">
            <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-[12px] bg-teal-soft text-teal">
              <Sparkles className="size-5" aria-hidden />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">
                Tell us about your business
              </h2>
              <p className="mt-1 text-sm text-text-secondary">
                What you do, what you offer, and how customers usually reach or
                book with you. A few clear sentences work best.
              </p>
            </div>
          </div>
          <Field label="Business description">
            <textarea
              className="min-h-44 w-full rounded-[var(--radius-md)] border border-border bg-surface px-3.5 py-3 text-sm leading-relaxed text-text-primary outline-none transition-[border-color,box-shadow] placeholder:text-text-muted focus:border-teal focus:ring-2 focus:ring-teal-soft disabled:bg-surface-muted"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="We run an HVAC company in Texas. We install and repair air conditioners, provide emergency repairs, schedule technician visits, and offer maintenance plans."
              disabled={busy || step === "analyzing"}
              aria-label="Business description"
            />
            <p className="mt-1.5 text-xs text-text-muted">
              {descriptionLen < 8
                ? `At least 8 characters (${descriptionLen}/8)`
                : `${descriptionLen} characters`}
            </p>
          </Field>
          {step === "analyzing" ? (
            <div
              className="space-y-4 rounded-[var(--radius-md)] border border-teal/20 bg-teal-soft/30 p-5"
              role="status"
              aria-live="polite"
            >
              <div className="flex items-center gap-2 text-sm font-semibold text-teal-deep">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Generating your business setup…
              </div>
              <ul className="space-y-2.5 text-sm">
                {ANALYZE_STAGES.map((label, i) => (
                  <li
                    key={label}
                    className={`flex items-center gap-2 ${
                      i <= analyzeStage ? "text-ink" : "text-text-muted"
                    }`}
                  >
                    {i < analyzeStage ? (
                      <Check
                        className="size-3.5 shrink-0 text-teal"
                        strokeWidth={2.5}
                        aria-hidden
                      />
                    ) : i === analyzeStage ? (
                      <Loader2
                        className="size-3.5 shrink-0 animate-spin text-teal"
                        aria-hidden
                      />
                    ) : (
                      <span
                        className="size-3.5 shrink-0 rounded-full border border-border"
                        aria-hidden
                      />
                    )}
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void onAnalyze()} disabled={!canGenerateNow}>
                <Sparkles className="mr-1.5 size-3.5" aria-hidden />
                Generate my setup
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setDescription("");
                  setAnswers({});
                }}
                disabled={busy || descriptionLen === 0}
              >
                <RotateCcw className="mr-1.5 size-3.5" aria-hidden />
                Clear
              </Button>
            </div>
          )}
        </Surface>
      )}

      {step === "clarify" && draft && (
        <Surface className="space-y-5 p-6">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              A few quick questions
            </h2>
            <p className="mt-1 text-sm text-text-secondary">
              Looks like a {industryLabel} business. Answer only what helps
              refine your workspace (up to 3).
            </p>
          </div>
          {(draft.clarifications || []).map((q) => (
            <fieldset key={q.id} className="space-y-2.5">
              <legend className="text-sm font-medium text-ink">{q.prompt}</legend>
              <div className="flex flex-wrap gap-2">
                {q.options.map((opt) => {
                  const selected = answers[q.id] === opt;
                  return (
                    <button
                      key={opt}
                      type="button"
                      aria-pressed={selected}
                      className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
                        selected
                          ? "border-teal bg-teal-soft font-medium text-teal-deep"
                          : "border-border bg-surface text-text-secondary hover:border-teal/40"
                      }`}
                      onClick={() =>
                        setAnswers((prev) => ({ ...prev, [q.id]: opt }))
                      }
                    >
                      {opt}
                    </button>
                  );
                })}
              </div>
            </fieldset>
          ))}
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              onClick={() => void onClarifyContinue()}
              disabled={busy || !canGenerate}
            >
              Continue
            </Button>
            <Button
              variant="ghost"
              onClick={() => setStep("describe")}
              disabled={busy}
            >
              Back
            </Button>
          </div>
        </Surface>
      )}

      {(step === "review" || step === "confirming") && draft && (
        <div className="space-y-4 pb-24">
          <Surface className="space-y-4 p-6">
            <h2 className="text-base font-semibold text-ink">Business profile</h2>
            <dl className="grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Industry
                </dt>
                <dd className="mt-1 text-sm text-ink">
                  {industryLabel}
                  <span className="text-text-muted">
                    {" "}
                    · {confidenceLabel(draft.business_profile.industry_confidence)}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Business model
                </dt>
                <dd className="mt-1 text-sm text-ink">
                  {draft.business_profile.business_models
                    .map((m) => humanizeKey(m))
                    .join(", ")}
                  <span className="text-text-muted">
                    {" "}
                    ·{" "}
                    {confidenceLabel(
                      draft.business_profile.business_model_confidence,
                    )}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Service area
                </dt>
                <dd className="mt-1 text-sm text-ink">
                  {draft.business_profile.service_area || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-text-muted">
                  Customer type
                </dt>
                <dd className="mt-1 text-sm text-ink">
                  {draft.business_profile.customer_type || "—"}
                </dd>
              </div>
            </dl>
          </Surface>

          <Surface className="space-y-4 p-6">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-ink">Modules</h2>
              <span className="text-xs text-text-muted">Tap to include or exclude</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {draft.modules.map((m: ModuleRec) => (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => toggleModule(m.key)}
                  className={`rounded-[var(--radius-md)] border p-3.5 text-left transition-colors ${
                    m.selected
                      ? "border-teal bg-teal-soft/40"
                      : "border-border bg-surface opacity-70 hover:opacity-100"
                  }`}
                  aria-pressed={m.selected}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-ink">
                      {humanizeKey(m.key)}
                    </span>
                    {m.selected ? (
                      <Check
                        className="size-4 shrink-0 text-teal"
                        strokeWidth={2.5}
                        aria-hidden
                      />
                    ) : null}
                  </div>
                  <p className="mt-1.5 text-xs text-text-secondary">{m.reason}</p>
                  <p className="mt-1 text-[11px] text-text-muted">
                    {confidenceLabel(m.confidence)}
                  </p>
                </button>
              ))}
            </div>
          </Surface>

          <Surface className="space-y-4 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-ink">Services</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={addService}
                disabled={!canUpdate}
              >
                <Plus className="mr-1 size-3.5" aria-hidden />
                Add
              </Button>
            </div>
            {draft.services.length === 0 ? (
              <EmptyState
                title="No services recommended"
                description="Add the services you offer."
              />
            ) : (
              <ul className="divide-y divide-border rounded-[var(--radius-md)] border border-border">
                {draft.services.map((s: ServiceRec, idx) => (
                  <li
                    key={`${s.name}-${idx}`}
                    className="flex items-start justify-between gap-3 px-3.5 py-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-ink">{s.name}</p>
                      <p className="text-xs text-text-secondary">{s.reason}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-text-muted hover:bg-surface-muted hover:text-ink"
                      aria-label={`Remove ${s.name}`}
                      onClick={() => removeService(idx)}
                      disabled={!canUpdate}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Surface>

          <Surface className="space-y-4 p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-semibold text-ink">Custom fields</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={addField}
                disabled={!canUpdate}
              >
                <Plus className="mr-1 size-3.5" aria-hidden />
                Add
              </Button>
            </div>
            {draft.custom_fields.length === 0 ? (
              <p className="text-sm text-text-muted">No custom fields recommended.</p>
            ) : (
              <ul className="divide-y divide-border rounded-[var(--radius-md)] border border-border">
                {draft.custom_fields.map((f: CustomFieldRec, idx) => (
                  <li
                    key={`${f.entity}-${f.field_key}-${idx}`}
                    className="flex items-start justify-between gap-3 px-3.5 py-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-ink">
                        {f.name}
                        <span className="text-xs font-normal text-text-muted">
                          {" "}
                          · {humanizeKey(f.entity)}
                        </span>
                      </p>
                      <p className="text-xs text-text-secondary">{f.reason}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-text-muted hover:bg-surface-muted hover:text-ink"
                      aria-label={`Remove ${f.name}`}
                      onClick={() => removeField(idx)}
                      disabled={!canUpdate}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Surface>

          {draft.product_categories.length > 0 ? (
            <Surface className="space-y-4 p-6">
              <div>
                <h2 className="text-base font-semibold text-ink">
                  Product categories
                </h2>
                <p className="mt-1 text-xs text-text-muted">
                  Categories only — no SKUs, prices, or inventory invented.
                </p>
              </div>
              <ul className="divide-y divide-border rounded-[var(--radius-md)] border border-border">
                {draft.product_categories.map((p: ProductCategoryRec, idx) => (
                  <li
                    key={`${p.name}-${idx}`}
                    className="flex items-start justify-between gap-3 px-3.5 py-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-ink">{p.name}</p>
                      <p className="text-xs text-text-secondary">{p.reason}</p>
                    </div>
                    <button
                      type="button"
                      className="rounded-md p-1.5 text-text-muted hover:bg-surface-muted hover:text-ink"
                      aria-label={`Remove ${p.name}`}
                      onClick={() => removeProduct(idx)}
                      disabled={!canUpdate}
                    >
                      <Trash2 className="size-4" />
                    </button>
                  </li>
                ))}
              </ul>
            </Surface>
          ) : null}

          <Surface className="space-y-4 p-6">
            <div className="flex items-start gap-3">
              <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-[12px] bg-teal-soft text-teal">
                <Bot className="size-5" aria-hidden />
              </div>
              <div>
                <h2 className="text-base font-semibold text-ink">
                  AI calling setup
                </h2>
                <p className="mt-1 text-sm text-text-secondary">
                  Purpose:{" "}
                  <span className="font-medium text-ink">
                    {humanizeKey(draft.ai_configuration.primary_purpose)}
                  </span>
                </p>
              </div>
            </div>
            {draft.ai_configuration.greeting_suggestion ? (
              <blockquote className="rounded-[var(--radius-md)] border border-teal/20 bg-teal-soft/30 px-4 py-3 text-sm italic text-ink">
                “{draft.ai_configuration.greeting_suggestion}”
              </blockquote>
            ) : null}
            <ul className="grid gap-2 sm:grid-cols-2">
              {draft.ai_configuration.capabilities.map((c) => (
                <li
                  key={c}
                  className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm text-ink"
                >
                  <Check
                    className="size-3.5 shrink-0 text-teal"
                    strokeWidth={2.5}
                    aria-hidden
                  />
                  {humanizeKey(c)}
                </li>
              ))}
            </ul>
            {draft.ai_configuration.risky_actions_disabled.length > 0 ? (
              <p className="text-xs text-text-muted">
                Risky actions stay off until you enable them later:{" "}
                {draft.ai_configuration.risky_actions_disabled
                  .map((a) => humanizeKey(a))
                  .join(", ")}
                .
              </p>
            ) : null}
          </Surface>

          <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-end gap-2 rounded-[var(--radius-md)] border border-border bg-surface/95 p-3 shadow-[var(--shadow-sm)] backdrop-blur">
            <Button
              variant="ghost"
              onClick={() => setStep("describe")}
              disabled={busy}
            >
              Edit description
            </Button>
            <Button
              variant="secondary"
              onClick={() => void onSaveDraft()}
              disabled={!canUpdate || busy}
            >
              Save draft
            </Button>
            <Button
              onClick={() => setConfirmOpen(true)}
              disabled={!canConfirm || busy || step === "confirming"}
            >
              {step === "confirming" ? (
                <>
                  <Loader2 className="mr-1.5 size-3.5 animate-spin" />
                  Saving…
                </>
              ) : (
                "Save and continue"
              )}
            </Button>
          </div>
        </div>
      )}

      {step === "done" && (
        <Surface className="space-y-5 p-6">
          <div className="flex items-start gap-3">
            <div className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-teal-soft text-teal">
              <Check className="size-5" strokeWidth={2.5} aria-hidden />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-ink">Setup saved</h2>
              <p className="mt-1 text-sm text-text-secondary">
                Your reviewed configuration was applied. Recommendations never
                change the workspace until you confirm.
              </p>
            </div>
          </div>
          {confirmResult ? (
            <dl className="grid gap-3 rounded-[var(--radius-md)] border border-border bg-surface-muted/30 p-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Industry
                </dt>
                <dd className="mt-1 font-medium text-ink">
                  {humanizeKey(String(confirmResult.industry ?? "—"))}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Modules enabled
                </dt>
                <dd className="mt-1 font-medium text-ink">
                  {Array.isArray(confirmResult.modules_enabled)
                    ? (confirmResult.modules_enabled as string[]).length
                    : 0}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Services created
                </dt>
                <dd className="mt-1 font-medium text-ink">
                  {String(confirmResult.services_created ?? 0)}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Custom fields
                </dt>
                <dd className="mt-1 font-medium text-ink">
                  {String(confirmResult.fields_created ?? 0)}
                </dd>
              </div>
            </dl>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={resetFlow}>
              Regenerate
            </Button>
            {confirmResult?.onboarding_complete === true ? (
              <Button onClick={() => router.replace("/dashboard")}>
                Go to dashboard
              </Button>
            ) : (
              <Button
                onClick={() => {
                  router.push(`${ONBOARDING_PATH}?manual=1`);
                }}
              >
                Continue to phone setup
              </Button>
            )}
          </div>
        </Surface>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title="Save business setup"
        description="This will apply the reviewed modules, services, and organization profile to your workspace."
        confirmLabel="Save and continue"
        onConfirm={() => void onConfirm()}
        onCancel={() => setConfirmOpen(false)}
      />
      </div>
    </OnboardingShell>
  );
}

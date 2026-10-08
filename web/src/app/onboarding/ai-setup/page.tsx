"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bot,
  Check,
  Loader2,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { hasPermission } from "@/lib/permissions";
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

export default function AiBusinessSetupPage() {
  const { user, loading, forbidden } = useAuth({
    permission: "business_setup.read",
  });
  const toast = useToast();
  const canGenerate = hasPermission(user, "business_setup.generate");
  const canUpdate = hasPermission(user, "business_setup.update");
  const canConfirm = hasPermission(user, "business_setup.confirm");

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

  if (loading || !user || fetching) {
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
  if (loadError) {
    return (
      <AppShell user={user}>
        <ErrorState message={loadError} onRetry={() => void load()} />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="AI Business Setup"
        description="Describe your business. Review recommendations. Confirm before anything is saved."
      />

      <div className="mb-6 flex flex-wrap gap-2 text-sm text-text-muted">
        {(
          [
            ["Describe", step === "describe"],
            ["Analyze", step === "analyzing" || step === "clarify"],
            ["Review", step === "review" || step === "confirming"],
            ["Confirm", step === "done"],
          ] as const
        ).map(([label, active]) => (
          <span
            key={label}
            className={`rounded-full px-3 py-1 ${
              active
                ? "bg-hero text-white"
                : "bg-surface-muted text-text-muted"
            }`}
          >
            {label}
          </span>
        ))}
      </div>

      {(step === "describe" || step === "analyzing") && (
        <Surface className="space-y-4">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-1 size-5 text-text" aria-hidden />
            <div>
              <h2 className="text-lg font-medium">Tell us about your business</h2>
              <p className="mt-1 text-sm text-text-muted">
                Write a few sentences in your own words. We will recommend modules,
                services, and AI calling setup — nothing is saved until you confirm.
              </p>
            </div>
          </div>
          <Field label="Business description">
            <textarea
              className="min-h-36 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder='e.g. "We are an HVAC company in Texas. We install and repair residential AC systems and offer annual maintenance plans."'
              disabled={busy || step === "analyzing"}
              aria-label="Business description"
            />
          </Field>
          {step === "analyzing" ? (
            <div className="space-y-3 rounded-lg border border-border bg-surface-muted/40 p-4" role="status" aria-live="polite">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Analyzing…
              </div>
              <ul className="space-y-2 text-sm">
                {ANALYZE_STAGES.map((label, i) => (
                  <li
                    key={label}
                    className={
                      i <= analyzeStage ? "text-text" : "text-text-muted"
                    }
                  >
                    {i < analyzeStage ? (
                      <Check className="mr-2 inline size-3.5" aria-hidden />
                    ) : i === analyzeStage ? (
                      <Loader2 className="mr-2 inline size-3.5 animate-spin" aria-hidden />
                    ) : null}
                    {label}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => void onAnalyze()}
                disabled={!canGenerate || description.trim().length < 8 || busy}
              >
                Analyze with AI
              </Button>
              <Button
                variant="ghost"
                onClick={() => {
                  setDescription("");
                  setAnswers({});
                }}
                disabled={busy}
              >
                <RotateCcw className="mr-1.5 size-3.5" aria-hidden />
                Clear
              </Button>
            </div>
          )}
        </Surface>
      )}

      {step === "clarify" && draft && (
        <Surface className="space-y-4">
          <h2 className="text-lg font-medium">A few quick questions</h2>
          <p className="text-sm text-text-muted">
            I understand you may be a {industryLabel} business. Answer only what
            helps refine your workspace (max 3).
          </p>
          {(draft.clarifications || []).map((q) => (
            <fieldset key={q.id} className="space-y-2">
              <legend className="text-sm font-medium">{q.prompt}</legend>
              <div className="flex flex-wrap gap-2">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    className={`rounded-full border px-3 py-1.5 text-sm ${
                      answers[q.id] === opt
                        ? "border-hero bg-hero text-white"
                        : "border-border bg-surface"
                    }`}
                    onClick={() =>
                      setAnswers((prev) => ({ ...prev, [q.id]: opt }))
                    }
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </fieldset>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void onClarifyContinue()} disabled={busy || !canGenerate}>
              Continue
            </Button>
            <Button variant="ghost" onClick={() => setStep("describe")} disabled={busy}>
              Back
            </Button>
          </div>
        </Surface>
      )}

      {(step === "review" || step === "confirming") && draft && (
        <div className="space-y-4">
          <Surface className="space-y-3">
            <h2 className="text-lg font-medium">Business profile</h2>
            <dl className="grid gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Industry
                </dt>
                <dd className="text-sm">
                  {industryLabel}{" "}
                  <span className="text-text-muted">
                    · {confidenceLabel(draft.business_profile.industry_confidence)}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Business model
                </dt>
                <dd className="text-sm">
                  {draft.business_profile.business_models
                    .map((m) => m.replace(/_/g, " "))
                    .join(", ")}{" "}
                  <span className="text-text-muted">
                    ·{" "}
                    {confidenceLabel(
                      draft.business_profile.business_model_confidence,
                    )}
                  </span>
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Service area
                </dt>
                <dd className="text-sm">
                  {draft.business_profile.service_area || "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-text-muted">
                  Customer type
                </dt>
                <dd className="text-sm">
                  {draft.business_profile.customer_type || "—"}
                </dd>
              </div>
            </dl>
          </Surface>

          <Surface className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-lg font-medium">Modules</h2>
              <span className="text-xs text-text-muted">
                Toggle to accept or remove
              </span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {draft.modules.map((m: ModuleRec) => (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => toggleModule(m.key)}
                  className={`rounded-lg border p-3 text-left transition ${
                    m.selected
                      ? "border-brand bg-surface-muted/50"
                      : "border-border opacity-60"
                  }`}
                  aria-pressed={m.selected}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{m.key}</span>
                    {m.selected ? (
                      <Check className="size-4 shrink-0" aria-hidden />
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-text-muted">{m.reason}</p>
                  <p className="mt-1 text-[11px] text-text-muted">
                    {confidenceLabel(m.confidence)}
                  </p>
                </button>
              ))}
            </div>
          </Surface>

          <Surface className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-medium">Services</h2>
              <Button variant="ghost" size="sm" onClick={addService} disabled={!canUpdate}>
                <Plus className="mr-1 size-3.5" aria-hidden />
                Add
              </Button>
            </div>
            {draft.services.length === 0 ? (
              <EmptyState title="No services recommended" description="Add services you offer." />
            ) : (
              <ul className="divide-y divide-border">
                {draft.services.map((s, idx) => (
                  <li
                    key={`${s.name}-${idx}`}
                    className="flex items-start justify-between gap-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium">{s.name}</p>
                      <p className="text-xs text-text-muted">{s.reason}</p>
                      <p className="text-[11px] text-text-muted">Price unset</p>
                    </div>
                    <button
                      type="button"
                      className="text-text-muted hover:text-text"
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

          <Surface className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-lg font-medium">Custom fields</h2>
              <Button variant="ghost" size="sm" onClick={addField} disabled={!canUpdate}>
                <Plus className="mr-1 size-3.5" aria-hidden />
                Add
              </Button>
            </div>
            {draft.custom_fields.length === 0 ? (
              <p className="text-sm text-text-muted">No custom fields recommended.</p>
            ) : (
              <ul className="divide-y divide-border">
                {draft.custom_fields.map((f, idx) => (
                  <li
                    key={`${f.entity}-${f.field_key}-${idx}`}
                    className="flex items-start justify-between gap-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium">
                        {f.name}{" "}
                        <span className="text-xs text-text-muted">
                          · {f.entity}
                        </span>
                      </p>
                      <p className="text-xs text-text-muted">{f.reason}</p>
                    </div>
                    <button
                      type="button"
                      className="text-text-muted hover:text-text"
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

          {draft.product_categories.length > 0 && (
            <Surface className="space-y-3">
              <h2 className="text-lg font-medium">Product categories</h2>
              <p className="text-xs text-text-muted">
                Categories only — no SKUs, prices, or inventory invented.
              </p>
              <ul className="divide-y divide-border">
                {draft.product_categories.map((p: ProductCategoryRec, idx) => (
                  <li
                    key={`${p.name}-${idx}`}
                    className="flex items-start justify-between gap-3 py-2"
                  >
                    <div>
                      <p className="text-sm font-medium">{p.name}</p>
                      <p className="text-xs text-text-muted">{p.reason}</p>
                    </div>
                    <button
                      type="button"
                      className="text-text-muted hover:text-text"
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
          )}

          <Surface className="space-y-3">
            <div className="flex items-center gap-2">
              <Bot className="size-5" aria-hidden />
              <h2 className="text-lg font-medium">AI calling setup</h2>
            </div>
            <p className="text-sm">
              Purpose:{" "}
              <span className="font-medium">
                {draft.ai_configuration.primary_purpose.replace(/_/g, " ")}
              </span>
            </p>
            {draft.ai_configuration.greeting_suggestion && (
              <p className="rounded-lg border border-border bg-surface-muted/30 p-3 text-sm italic">
                “{draft.ai_configuration.greeting_suggestion}”
              </p>
            )}
            <ul className="grid gap-1 sm:grid-cols-2">
              {draft.ai_configuration.capabilities.map((c) => (
                <li key={c} className="text-sm">
                  <Check className="mr-1.5 inline size-3.5" aria-hidden />
                  {c.replace(/_/g, " ")}
                </li>
              ))}
            </ul>
            <p className="text-xs text-text-muted">
              Risky actions stay disabled until you enable them separately:{" "}
              {draft.ai_configuration.risky_actions_disabled.join(", ")}.
            </p>
          </Surface>

          <div className="flex flex-wrap gap-2 pb-8">
            <Button
              variant="ghost"
              onClick={() => setStep("describe")}
              disabled={busy}
            >
              Back
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
                  Confirming…
                </>
              ) : (
                "Confirm business setup"
              )}
            </Button>
          </div>
        </div>
      )}

      {step === "done" && (
        <Surface className="space-y-4">
          <div className="flex items-center gap-2 text-emerald-700">
            <Check className="size-5" aria-hidden />
            <h2 className="text-lg font-medium">Setup complete</h2>
          </div>
          <p className="text-sm text-text-muted">
            Your reviewed configuration was applied through existing domain services.
            AI recommendations never mutate configuration without confirmation.
          </p>
          {confirmResult && (
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-text-muted">Industry</dt>
                <dd>{String(confirmResult.industry ?? "—")}</dd>
              </div>
              <div>
                <dt className="text-text-muted">Modules enabled</dt>
                <dd>
                  {Array.isArray(confirmResult.modules_enabled)
                    ? (confirmResult.modules_enabled as string[]).length
                    : 0}
                </dd>
              </div>
              <div>
                <dt className="text-text-muted">Services created</dt>
                <dd>{String(confirmResult.services_created ?? 0)}</dd>
              </div>
              <div>
                <dt className="text-text-muted">Custom fields</dt>
                <dd>{String(confirmResult.fields_created ?? 0)}</dd>
              </div>
            </dl>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" onClick={resetFlow}>
              Start over
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                window.location.href = "/onboarding";
              }}
            >
              Continue onboarding
            </Button>
          </div>
        </Surface>
      )}

      <ConfirmDialog
        open={confirmOpen}
        title="Confirm business setup"
        description="This will apply the reviewed modules, services, and organization profile. Double-submit is safe (idempotent)."
        confirmLabel="Confirm setup"
        onConfirm={() => void onConfirm()}
        onCancel={() => setConfirmOpen(false)}
      />
    </AppShell>
  );
}

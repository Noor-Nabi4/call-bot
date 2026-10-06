"use client";

import { useCallback, useEffect, useState } from "react";
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
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
  Surface,
  useToast,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

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

export default function OnboardingPage() {
  const { user, loading, forbidden } = useAuth({
    permission: "organization.read",
  });
  const canUpdate = Boolean(
    user?.permissions?.some((p) => p.key === "organization.update"),
  );
  const toast = useToast();
  const [state, setState] = useState<OnboardingState | null>(null);
  const [fetching, setFetching] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [draftNote, setDraftNote] = useState("");

  const load = useCallback(async () => {
    const data = await api<{ onboarding: OnboardingState }>(
      "/api/admin/organization/onboarding",
    );
    setState(data.onboarding);
    const note = data.onboarding.state_data?.draft_note;
    setDraftNote(typeof note === "string" ? note : "");
    setLoadError(null);
  }, []);

  useEffect(() => {
    if (!user) return;
    load()
      .catch((e) => setLoadError(safeUserError(e, errors.loadFailed)))
      .finally(() => setFetching(false));
  }, [user, load]);

  async function mutate(path: string, init?: RequestInit) {
    if (!canUpdate) return;
    setBusy(true);
    try {
      const data = await api<{ onboarding: OnboardingState }>(path, init);
      setState(data.onboarding);
      toast.push("Onboarding saved", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
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

  const resume = state ? resumeTarget(state) : null;
  const closed =
    state?.status === "COMPLETED" || state?.status === "SKIPPED";

  return (
    <AppShell user={user}>
      <PageHeader
        title="Onboarding"
        description="Persistent organization setup progress. Domain data still lives in its own settings."
      />

      {fetching ? (
        <LoadingSkeleton rows={6} />
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
      ) : state ? (
        <div className="space-y-6">
          <Surface className="space-y-4 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={state.status} />
              <span className="text-sm text-text-secondary">
                {progressLabel(state)}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
              <div
                className="h-full rounded-full bg-teal transition-all"
                style={{ width: `${state.progress_percent}%` }}
              />
            </div>
            {state.can_resume && resume ? (
              <p className="text-sm text-text-primary">
                Resume at{" "}
                <strong>{resume.replaceAll("_", " ")}</strong>
              </p>
            ) : null}
            {canUpdate && !closed ? (
              <div className="flex flex-wrap gap-2">
                {resume ? (
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      mutate("/api/admin/organization/onboarding", {
                        method: "PATCH",
                        body: JSON.stringify({ current_step: resume }),
                      })
                    }
                  >
                    Focus resume step
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    mutate("/api/admin/organization/onboarding/skip", {
                      method: "POST",
                    })
                  }
                >
                  Skip onboarding
                </Button>
              </div>
            ) : null}
          </Surface>

          {canUpdate && !closed ? (
            <Surface className="space-y-3 p-5">
              <h2 className="text-sm font-semibold text-text-primary">
                Partial draft
              </h2>
              <p className="text-sm text-text-secondary">
                Saves into onboarding state_data only — not a substitute for
                organization profile fields.
              </p>
              <textarea
                className="min-h-24 w-full rounded-[var(--radius-md)] border border-border bg-surface p-3 text-sm text-text-primary"
                value={draftNote}
                onChange={(e) => setDraftNote(e.target.value)}
                placeholder="Notes for yourself while setting up…"
              />
              <Button
                type="button"
                disabled={busy}
                onClick={() =>
                  mutate("/api/admin/organization/onboarding", {
                    method: "PATCH",
                    body: JSON.stringify({
                      state_data: { draft_note: draftNote || null },
                    }),
                  })
                }
              >
                Save draft
              </Button>
            </Surface>
          ) : null}

          <Surface className="p-5">
            <h2 className="mb-4 text-sm font-semibold text-text-primary">
              Steps
            </h2>
            <ul className="space-y-3">
              {state.steps.map((step) => (
                <li
                  key={step.key}
                  className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-3 last:border-0"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-text-primary">
                        {step.title}
                      </span>
                      <StatusPill status={step.state} />
                      <span className="text-xs text-text-muted">
                        {step.required ? "required" : "optional"}
                      </span>
                    </div>
                    {step.description ? (
                      <p className="text-sm text-text-secondary">
                        {step.description}
                      </p>
                    ) : null}
                  </div>
                  {canUpdate && !closed ? (
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        size="sm"
                        disabled={busy || step.state === "completed"}
                        onClick={() =>
                          mutate(
                            `/api/admin/organization/onboarding/steps/${step.key}/complete`,
                            { method: "POST" },
                          )
                        }
                      >
                        Complete
                      </Button>
                      {!step.required ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          disabled={busy || step.state === "skipped"}
                          onClick={() =>
                            mutate(
                              `/api/admin/organization/onboarding/steps/${step.key}/skip`,
                              { method: "POST" },
                            )
                          }
                        >
                          Skip
                        </Button>
                      ) : null}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </Surface>
        </div>
      ) : null}
    </AppShell>
  );
}

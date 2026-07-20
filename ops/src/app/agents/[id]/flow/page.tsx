"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { getAgentProfile, updateAgentProfile } from "@/lib/api";
import type { CallFlow, CallFlowStep } from "@/types";
import { errors, callFlow as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Surface,
  Textarea,
  useToast,
} from "@/components/ui";

const STEP_TYPES: CallFlowStep["type"][] = [
  "greeting",
  "qualify",
  "book",
  "faq",
  "handoff",
  "custom",
];

function newStep(): CallFlowStep {
  return {
    id: `step-${Math.random().toString(36).slice(2, 10)}`,
    type: "custom",
    label: "New step",
    instruction: "",
    enabled: true,
  };
}

export default function AgentCallFlowPage() {
  const params = useParams<{ id: string }>();
  const profileId = params.id;
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [name, setName] = useState("");
  const [flow, setFlow] = useState<CallFlow | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await getAgentProfile(profileId);
    setName(data.profile.name);
    setFlow(
      data.profile.call_flow || {
        version: 1,
        steps: [],
      },
    );
  }, [profileId]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  function updateStep(index: number, patch: Partial<CallFlowStep>) {
    if (!flow) return;
    const steps = flow.steps.map((step, i) =>
      i === index ? { ...step, ...patch } : step,
    );
    setFlow({ ...flow, steps });
  }

  function moveStep(index: number, delta: number) {
    if (!flow) return;
    const target = index + delta;
    if (target < 0 || target >= flow.steps.length) return;
    const steps = [...flow.steps];
    const [item] = steps.splice(index, 1);
    steps.splice(target, 0, item);
    setFlow({ ...flow, steps });
  }

  function removeStep(index: number) {
    if (!flow) return;
    setFlow({
      ...flow,
      steps: flow.steps.filter((_, i) => i !== index),
    });
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!flow) return;
    setSaving(true);
    setError(null);
    try {
      const data = await updateAgentProfile(profileId, { call_flow: flow });
      setFlow(data.profile.call_flow || flow);
      toast.push(copy.saved, "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setSaving(false);
    }
  }

  if (loading || !user || fetching || !flow) {
    return <LoadingSkeleton rows={6} />;
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={`${copy.title}: ${name}`}
        description={copy.description}
        actions={
          <Link
            href={`/agents/${profileId}`}
            className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
          >
            {copy.backToAgent}
          </Link>
        }
      />

      {error ? (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      ) : null}

      <form onSubmit={onSave} className="space-y-4">
        <Surface className="p-4">
          <p className="m-0 text-sm text-text-secondary">{copy.hint}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() =>
                setFlow({ ...flow, steps: [...flow.steps, newStep()] })
              }
            >
              <Plus className="mr-1 size-4" />
              {copy.addStep}
            </Button>
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? copy.saving : copy.save}
            </Button>
          </div>
        </Surface>

        {flow.steps.length === 0 ? (
          <Surface className="p-6 text-sm text-text-secondary">
            {copy.empty}
          </Surface>
        ) : (
          <ol className="m-0 list-none space-y-3 p-0">
            {flow.steps.map((step, index) => (
              <li key={step.id}>
                <Surface className="p-4">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <p className="m-0 text-xs font-medium uppercase tracking-wide text-text-muted">
                      {copy.step} {index + 1}
                    </p>
                    <div className="flex gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label="Move up"
                        disabled={index === 0}
                        onClick={() => moveStep(index, -1)}
                      >
                        <ArrowUp className="size-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label="Move down"
                        disabled={index === flow.steps.length - 1}
                        onClick={() => moveStep(index, 1)}
                      >
                        <ArrowDown className="size-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-danger"
                        aria-label="Remove step"
                        onClick={() => removeStep(index)}
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label={copy.label}>
                      <Input
                        value={step.label}
                        onChange={(e) =>
                          updateStep(index, { label: e.target.value })
                        }
                        required
                      />
                    </Field>
                    <Field label={copy.type}>
                      <Select
                        value={step.type}
                        onChange={(e) =>
                          updateStep(index, { type: e.target.value })
                        }
                      >
                        {STEP_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label={copy.status}>
                      <Select
                        value={step.enabled ? "enabled" : "disabled"}
                        onChange={(e) =>
                          updateStep(index, {
                            enabled: e.target.value === "enabled",
                          })
                        }
                      >
                        <option value="enabled">{copy.enabled}</option>
                        <option value="disabled">{copy.disabled}</option>
                      </Select>
                    </Field>
                  </div>
                  <div className="mt-3">
                    <Field label={copy.instruction}>
                      <Textarea
                        rows={3}
                        value={step.instruction || ""}
                        onChange={(e) =>
                          updateStep(index, { instruction: e.target.value })
                        }
                      />
                    </Field>
                  </div>
                </Surface>
              </li>
            ))}
          </ol>
        )}
      </form>
    </AppShell>
  );
}

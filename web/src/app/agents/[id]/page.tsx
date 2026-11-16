"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { PhoneCall, ShieldAlert } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { hasPermission } from "@/lib/permissions";
import {
  applyAgentTemplate,
  listIndustryTemplates,
  listPhoneNumbers,
  type IndustryTemplate,
  type PhoneNumber,
} from "@/lib/api";
import {
  activateAgentConfig,
  getAgentConfig,
  getAgentConfigCatalog,
  updateAgentConfig,
  type AgentConfig,
  type AgentConfigCatalog,
  type CapabilityState,
} from "@/lib/api/agent-config";
import { categoryLabel, riskLabel } from "@/lib/api/agent-config-format";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ConfirmDialog,
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

const STEPS = [
  "Profile",
  "Capabilities",
  "Hours & after-hours",
  "Transfers",
  "Review",
  "Phones",
] as const;

const DAY_KEYS = [
  ["mon", "Monday"],
  ["tue", "Tuesday"],
  ["wed", "Wednesday"],
  ["thu", "Thursday"],
  ["fri", "Friday"],
  ["sat", "Saturday"],
  ["sun", "Sunday"],
] as const;

function hoursLine(intervals: string[][] | undefined): string {
  if (!intervals?.length) return "Closed";
  return intervals.map((pair) => `${pair[0]} – ${pair[1]}`).join(", ");
}

export default function AgentBuilderPage() {
  const params = useParams<{ id: string }>();
  const profileId = params.id;
  const { user, loading, forbidden } = useAuth({
    permission: "agents.manage",
  });
  const toast = useToast();
  const canUpdate =
    hasPermission(user, "agent_config.update") ||
    hasPermission(user, "agents.manage");
  const canActivate =
    hasPermission(user, "agent_config.activate") ||
    hasPermission(user, "agents.manage");
  const canCaps =
    hasPermission(user, "agent_capabilities.update") ||
    hasPermission(user, "agents.manage");

  const [step, setStep] = useState(0);
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [catalog, setCatalog] = useState<AgentConfigCatalog | null>(null);
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [phones, setPhones] = useState<PhoneNumber[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);

  const load = useCallback(async () => {
    const [cfg, cat, templateData, phoneData] = await Promise.all([
      getAgentConfig(profileId),
      getAgentConfigCatalog(),
      listIndustryTemplates(),
      listPhoneNumbers(),
    ]);
    setConfig(cfg.config);
    setCatalog(cat.catalog);
    setTemplates(templateData.templates);
    setPhones(phoneData.items);
  }, [profileId]);

  useEffect(() => {
    if (!user) return;
    setFetching(true);
    load()
      .catch((err) => setError(safeUserError(err, "Could not load agent")))
      .finally(() => setFetching(false));
  }, [user, load]);

  const linkedPhones = useMemo(
    () =>
      phones.filter(
        (p) =>
          p.agent_profile_id === profileId ||
          (!p.agent_profile_id && config?.is_default),
      ),
    [phones, profileId, config?.is_default],
  );

  const capsByCategory = useMemo(() => {
    const map = new Map<string, CapabilityState[]>();
    for (const state of config?.capability_states || []) {
      const list = map.get(state.category) || [];
      list.push(state);
      map.set(state.category, list);
    }
    return map;
  }, [config]);

  function setField<K extends keyof AgentConfig>(key: K, value: AgentConfig[K]) {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function onSave(e?: FormEvent) {
    e?.preventDefault();
    if (!config || !canUpdate) return;
    setSaving(true);
    try {
      const res = await updateAgentConfig(profileId, {
        name: config.name,
        assistant_name: config.assistant_name,
        voice: config.voice,
        language: config.language,
        tone: config.tone,
        greeting: config.greeting,
        custom_instructions: config.custom_instructions,
        business_description: config.business_description,
        business_hours_summary: config.business_hours_summary,
        business_hours: config.business_hours,
        handoff_rules_text: config.handoff_rules_text,
        supported_languages: config.supported_languages,
        response_style: config.response_style,
        status: config.status === "active" ? undefined : config.status,
        capabilities: canCaps ? config.capabilities : undefined,
        transfer_rules: config.transfer_rules,
        escalation_rules: config.escalation_rules,
        after_hours_behavior: config.after_hours_behavior,
      });
      setConfig(res.config);
      toast.push("Agent configuration saved", "success");
    } catch (err) {
      toast.push(safeUserError(err, "Could not save agent"), "error");
    } finally {
      setSaving(false);
    }
  }

  async function onActivate() {
    if (!canActivate) return;
    setActivateOpen(false);
    setSaving(true);
    try {
      await onSave();
      const res = await activateAgentConfig(profileId);
      setConfig(res.config);
      toast.push("Configuration activated for new calls", "success");
    } catch (err) {
      toast.push(safeUserError(err, "Could not activate"), "error");
    } finally {
      setSaving(false);
    }
  }

  async function onApplyTemplate(key: string) {
    try {
      await applyAgentTemplate(profileId, key, true);
      await load();
      toast.push(`Applied ${key} template`, "success");
    } catch (err) {
      toast.push(safeUserError(err, "Could not apply template"), "error");
    }
  }

  function toggleCapability(key: string) {
    if (!config || !canCaps) return;
    const state = config.capability_states.find((c) => c.key === key);
    if (state && !state.available && !config.capabilities[key]) return;
    setConfig({
      ...config,
      capabilities: {
        ...config.capabilities,
        [key]: !config.capabilities[key],
      },
    });
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
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
  if (fetching || !config || !catalog) {
    return (
      <AppShell user={user}>
        {error ? (
          <ErrorState message={error} onRetry={() => void load()} />
        ) : (
          <LoadingSkeleton rows={8} />
        )}
      </AppShell>
    );
  }

  const greetingPreview =
    config.greeting ||
    `Thanks for calling. This is ${config.assistant_name || "your assistant"}. How can I help you today?`;

  return (
    <AppShell user={user}>
      <PageHeader
        title={config.name}
        description={`v${config.profile_version} · ${config.status}${config.is_default ? " · default" : ""}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/agents">
              <Button variant="secondary" size="sm">
                All agents
              </Button>
            </Link>
            <Link href={`/agents/${profileId}/flow`}>
              <Button variant="secondary" size="sm">
                Call flow
              </Button>
            </Link>
            <Link href={`/playground?profile=${encodeURIComponent(profileId)}`}>
              <Button variant="secondary" size="sm">
                <PhoneCall className="size-3.5" aria-hidden />
                Test call
              </Button>
            </Link>
            {canActivate ? (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setActivateOpen(true)}
                disabled={saving}
              >
                Activate
              </Button>
            ) : null}
            <Button size="sm" onClick={() => void onSave()} disabled={saving || !canUpdate}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      <div className="mt-5 flex flex-wrap gap-2">
        {STEPS.map((label, idx) => (
          <button
            key={label}
            type="button"
            onClick={() => setStep(idx)}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
              step === idx
                ? "bg-brand text-white"
                : "bg-surface-muted text-text-secondary hover:bg-fog-deep"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={(e) => void onSave(e)} className="mt-5">
        <Surface className="ops-surface-rise space-y-4 p-5">
          {step === 0 ? (
            <>
              <Field label="Profile name">
                <Input
                  value={config.name}
                  onChange={(e) => setField("name", e.target.value)}
                  disabled={!canUpdate}
                />
              </Field>
              <Field label="Agent name (spoken)">
                <Input
                  value={config.assistant_name || ""}
                  onChange={(e) => setField("assistant_name", e.target.value)}
                  disabled={!canUpdate}
                  placeholder="Alex"
                />
              </Field>
              <Field label="Voice">
                <Select
                  value={config.voice || "marin"}
                  onChange={(e) => setField("voice", e.target.value)}
                  disabled={!canUpdate}
                >
                  {catalog.voices.map((v) => (
                    <option key={v.key} value={v.key}>
                      {v.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Language">
                <Select
                  value={config.language || "en"}
                  onChange={(e) => setField("language", e.target.value)}
                  disabled={!canUpdate}
                >
                  {catalog.languages.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Tone">
                <Select
                  value={config.tone || "professional"}
                  onChange={(e) => setField("tone", e.target.value)}
                  disabled={!canUpdate}
                >
                  {catalog.tones.map((t) => (
                    <option key={t.key} value={t.key}>
                      {t.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Greeting">
                <textarea
                  className="min-h-24 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                  value={config.greeting || ""}
                  onChange={(e) => setField("greeting", e.target.value)}
                  disabled={!canUpdate}
                  aria-label="Greeting"
                />
              </Field>
              <div className="rounded-lg border border-border bg-surface-muted/40 p-3 text-sm italic">
                Preview: “{greetingPreview}”
              </div>
              <Field label="Custom style (untrusted; cannot bypass tool auth)">
                <textarea
                  className="min-h-20 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                  value={config.custom_instructions || ""}
                  onChange={(e) => setField("custom_instructions", e.target.value)}
                  disabled={!canUpdate}
                  aria-label="Custom instructions"
                />
              </Field>
              <Field label="Apply industry template">
                <Select
                  defaultValue=""
                  onChange={(e) => {
                    if (e.target.value) void onApplyTemplate(e.target.value);
                  }}
                  disabled={!canUpdate}
                >
                  <option value="">Choose template…</option>
                  {templates.map((tpl) => (
                    <option key={tpl.key} value={tpl.key}>
                      {tpl.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </>
          ) : null}

          {step === 1 ? (
            <div className="space-y-6">
              <p className="text-sm text-text-muted">
                Capabilities map to existing AI tools. Disabled capabilities cannot
                mutate data even if the model requests a tool. Enabling a capability
                does not bypass RBAC, confirmation, or tenant ownership checks.
              </p>
              {[...capsByCategory.entries()].map(([category, states]) => (
                <div key={category} className="space-y-2">
                  <h3 className="text-sm font-semibold">{categoryLabel(category)}</h3>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {states.map((state) => (
                      <button
                        key={state.key}
                        type="button"
                        disabled={!canCaps || (!state.available && !config.capabilities[state.key])}
                        onClick={() => toggleCapability(state.key)}
                        className={`rounded-lg border p-3 text-left transition ${
                          config.capabilities[state.key]
                            ? "border-brand bg-surface-muted/50"
                            : "border-border opacity-70"
                        }`}
                        aria-pressed={Boolean(config.capabilities[state.key])}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-medium">
                            {state.display_name}
                          </span>
                          <span className="text-[11px] text-text-muted">
                            {riskLabel(state.risk_level)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-text-muted">
                          {state.description}
                        </p>
                        {state.confirmation_required ? (
                          <p className="mt-2 text-xs text-text-muted">
                            Caller confirmation required before execution
                          </p>
                        ) : null}
                        {!state.available ? (
                          <p className="mt-2 flex items-center gap-1 text-xs text-amber-700">
                            <ShieldAlert className="size-3.5" aria-hidden />
                            {state.unavailable_reason || "Unavailable"}
                          </p>
                        ) : null}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {step === 2 ? (
            <>
              <p className="text-sm text-text-muted">
                Prompt summary uses these hours. Canonical scheduling hours remain
                under Appointments → Business hours.
              </p>
              <Field label="Business hours summary">
                <Input
                  value={config.business_hours_summary || ""}
                  onChange={(e) =>
                    setField("business_hours_summary", e.target.value)
                  }
                  disabled={!canUpdate}
                />
              </Field>
              <div className="space-y-2">
                {DAY_KEYS.map(([key, label]) => (
                  <div
                    key={key}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm"
                  >
                    <span className="font-medium">{label}</span>
                    <span className="text-text-muted">
                      {hoursLine(config.business_hours?.[key])}
                    </span>
                  </div>
                ))}
              </div>
              <Field label="After-hours behavior">
                <Select
                  value={config.after_hours_behavior || "take_message"}
                  onChange={(e) =>
                    setField("after_hours_behavior", e.target.value)
                  }
                  disabled={!canUpdate}
                >
                  {catalog.after_hours_behaviors.map((b) => (
                    <option key={b.key} value={b.key}>
                      {b.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Link href="/crm/scheduling" className="text-sm text-brand underline">
                Edit canonical business hours
              </Link>
            </>
          ) : null}

          {step === 3 ? (
            <>
              <h3 className="text-sm font-semibold">Transfer when</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {catalog.transfer_rules.map((rule) => (
                  <label
                    key={rule.key}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
                  >
                    <span>{rule.display_name}</span>
                    <input
                      type="checkbox"
                      checked={Boolean(config.transfer_rules?.[rule.key])}
                      disabled={!canUpdate}
                      onChange={(e) =>
                        setField("transfer_rules", {
                          ...config.transfer_rules,
                          [rule.key]: e.target.checked,
                        })
                      }
                    />
                  </label>
                ))}
              </div>
              <h3 className="mt-4 text-sm font-semibold">Escalate when</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {catalog.escalation_rules.map((rule) => (
                  <label
                    key={rule.key}
                    className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
                  >
                    <span>{rule.display_name}</span>
                    <input
                      type="checkbox"
                      checked={Boolean(config.escalation_rules?.[rule.key])}
                      disabled={!canUpdate}
                      onChange={(e) =>
                        setField("escalation_rules", {
                          ...config.escalation_rules,
                          [rule.key]: e.target.checked,
                        })
                      }
                    />
                  </label>
                ))}
              </div>
              <Field label="Handoff guidance (prompt text)">
                <textarea
                  className="min-h-20 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm"
                  value={config.handoff_rules_text || ""}
                  onChange={(e) => setField("handoff_rules_text", e.target.value)}
                  disabled={!canUpdate}
                  aria-label="Handoff rules"
                />
              </Field>
              <p className="text-xs text-text-muted">
                Destinations and warm/cold mode use existing Handoff settings — not
                duplicated here.
              </p>
              <Link href="/handoff" className="text-sm text-brand underline">
                Open handoff settings
              </Link>
            </>
          ) : null}

          {step === 4 ? (
            <div className="space-y-3 text-sm">
              <h3 className="font-semibold">Review</h3>
              <dl className="grid gap-2 sm:grid-cols-2">
                <div>
                  <dt className="text-text-muted">Agent</dt>
                  <dd>{config.assistant_name || config.name}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">Voice / language / tone</dt>
                  <dd>
                    {config.voice} · {config.language} · {config.tone}
                  </dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-text-muted">Greeting</dt>
                  <dd className="italic">“{greetingPreview}”</dd>
                </div>
                <div>
                  <dt className="text-text-muted">After hours</dt>
                  <dd>{config.after_hours_behavior}</dd>
                </div>
                <div>
                  <dt className="text-text-muted">Enabled capabilities</dt>
                  <dd>
                    {Object.entries(config.capabilities)
                      .filter(([, on]) => on)
                      .map(([k]) => k)
                      .join(", ") || "None"}
                  </dd>
                </div>
              </dl>
              <p className="text-xs text-text-muted">
                Saving updates the profile (version bump). Activate publishes for
                new calls; in-flight calls keep their resolved snapshot.
              </p>
            </div>
          ) : null}

          {step === 5 ? (
            <div className="space-y-3">
              <p className="text-sm text-text-secondary">
                Assign numbers on the Phones page. Numbers without an assignment use
                the tenant default agent.
              </p>
              {linkedPhones.length === 0 ? (
                <p className="text-sm text-text-muted">No phones linked yet.</p>
              ) : (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {linkedPhones.map((phone) => (
                    <li key={phone.id} className="px-3 py-2 text-sm">
                      <span className="font-medium">{phone.e164}</span>
                      <span className="ml-2 text-text-muted">
                        {phone.connection_status} · {phone.verification_status}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <Link href="/phones">
                <Button variant="secondary" size="sm">
                  Open phone management
                </Button>
              </Link>
            </div>
          ) : null}

          <div className="flex justify-between pt-2">
            <Button
              type="button"
              variant="secondary"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
            >
              Back
            </Button>
            <div className="flex gap-2">
              {step < STEPS.length - 1 ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
                >
                  Next
                </Button>
              ) : null}
              <Button type="submit" disabled={saving || !canUpdate}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </div>
        </Surface>
      </form>

      <ConfirmDialog
        open={activateOpen}
        title="Activate agent configuration"
        description="New calls will use this configuration. Existing calls keep their resolved snapshot."
        confirmLabel="Activate"
        onConfirm={() => void onActivate()}
        onCancel={() => setActivateOpen(false)}
      />
    </AppShell>
  );
}

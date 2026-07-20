"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { PhoneCall } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  applyAgentTemplate,
  createTestCall,
  getAgentProfile,
  listIndustryTemplates,
  listPhoneNumbers,
  updateAgentProfile,
  type AgentProfile,
  type IndustryTemplate,
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

const STEPS = [
  "Identity",
  "Conversation",
  "Business",
  "Behavior",
  "Tools",
  "Phones",
] as const;

function listToText(values: string[] | null | undefined): string {
  return (values || []).join(", ");
}

function textToList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function AgentBuilderPage() {
  const params = useParams<{ id: string }>();
  const profileId = params.id;
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<AgentProfile | null>(null);
  const [businessName, setBusinessName] = useState("");
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [phones, setPhones] = useState<PhoneNumber[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saving, setSaving] = useState(false);
  const [supportedLanguagesText, setSupportedLanguagesText] = useState("en");
  const [serviceAreasText, setServiceAreasText] = useState("");
  const [restrictedTopicsText, setRestrictedTopicsText] = useState("");
  const [testInfo, setTestInfo] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [profileData, templateData, phoneData] = await Promise.all([
      getAgentProfile(profileId),
      listIndustryTemplates(),
      listPhoneNumbers(),
    ]);
    setForm(profileData.profile);
    setBusinessName(profileData.business_name);
    setTemplates(templateData.templates);
    setPhones(phoneData.items);
    setSupportedLanguagesText(
      listToText(
        profileData.profile.supported_languages?.length
          ? profileData.profile.supported_languages
          : ["en"],
      ),
    );
    setServiceAreasText(listToText(profileData.profile.service_areas));
    setRestrictedTopicsText(listToText(profileData.profile.restricted_topics));
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
          (!p.agent_profile_id && form?.is_default),
      ),
    [phones, profileId, form?.is_default],
  );

  function setField<K extends keyof AgentProfile>(key: K, value: AgentProfile[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function onSave(e?: FormEvent) {
    e?.preventDefault();
    if (!form) return;
    setSaving(true);
    try {
      const updated = await updateAgentProfile(profileId, {
        name: form.name,
        agent_type: form.agent_type,
        voice: form.voice,
        language: form.language,
        greeting: form.greeting,
        assistant_name: form.assistant_name,
        business_description: form.business_description,
        tone: form.tone,
        supported_languages: textToList(supportedLanguagesText),
        response_style: form.response_style,
        service_areas: textToList(serviceAreasText),
        business_hours_summary: form.business_hours_summary,
        booking_rules: form.booking_rules,
        pricing_disclosure_policy: form.pricing_disclosure_policy,
        handoff_rules_text: form.handoff_rules_text,
        restricted_topics: textToList(restrictedTopicsText),
        custom_instructions: form.custom_instructions,
        enabled_tools: form.enabled_tools,
      });
      setForm(updated.profile);
      toast.push("Agent saved", "success");
    } catch (err) {
      toast.push(safeUserError(err, "Could not save agent"), "error");
    } finally {
      setSaving(false);
    }
  }

  async function onApplyTemplate(key: string) {
    try {
      const updated = await applyAgentTemplate(profileId, key, true);
      setForm(updated.profile);
      setSupportedLanguagesText(
        listToText(updated.profile.supported_languages || ["en"]),
      );
      setServiceAreasText(listToText(updated.profile.service_areas));
      setRestrictedTopicsText(listToText(updated.profile.restricted_topics));
      toast.push(`Applied ${key} template`, "success");
    } catch (err) {
      toast.push(safeUserError(err, "Could not apply template"), "error");
    }
  }

  async function onTestCall() {
    try {
      const session = await createTestCall(profileId);
      setTestInfo(
        `Room ${session.room_name} ready. Connect with LiveKit using the issued participant token (expires soon). Server: ${session.server_url}`,
      );
      toast.push("Test call session created", "success");
    } catch (err) {
      toast.push(safeUserError(err, "Could not start test call"), "error");
    }
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  if (fetching || !form) {
    return (
      <AppShell user={user}>
        <LoadingSkeleton rows={8} />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={form.name}
        description={`${businessName} · ${form.agent_type}${form.is_default ? " · default fallback" : ""}`}
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
            <Button variant="secondary" size="sm" onClick={onTestCall}>
              <PhoneCall className="size-3.5" aria-hidden />
              Test call
            </Button>
            <Button size="sm" onClick={() => onSave()} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}
      {testInfo ? (
        <p className="mt-3 rounded-lg border border-brand/30 bg-brand-soft px-3 py-2 text-sm text-text-secondary">
          {testInfo}
        </p>
      ) : null}

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

      <form onSubmit={onSave} className="mt-5">
        <Surface className="ops-surface-rise space-y-4 p-5">
          {step === 0 ? (
            <>
              <Field label="Profile name">
                <Input
                  value={form.name}
                  onChange={(e) => setField("name", e.target.value)}
                />
              </Field>
              <Field label="Assistant name">
                <Input
                  value={form.assistant_name || ""}
                  onChange={(e) => setField("assistant_name", e.target.value)}
                />
              </Field>
              <Field label="Voice">
                <Input
                  value={form.voice || "marin"}
                  onChange={(e) => setField("voice", e.target.value)}
                />
              </Field>
              <Field label="Greeting">
                <Input
                  value={form.greeting || ""}
                  onChange={(e) => setField("greeting", e.target.value)}
                />
              </Field>
              <Field label="Apply industry template">
                <Select
                  defaultValue=""
                  onChange={(e) => {
                    if (e.target.value) onApplyTemplate(e.target.value);
                  }}
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
            <>
              <Field label="Tone">
                <Select
                  value={form.tone || "professional"}
                  onChange={(e) => setField("tone", e.target.value)}
                >
                  <option value="professional">Professional</option>
                  <option value="friendly">Friendly</option>
                  <option value="warm">Warm</option>
                  <option value="formal">Formal</option>
                  <option value="casual">Casual</option>
                </Select>
              </Field>
              <Field label="Response style">
                <Select
                  value={form.response_style || "concise"}
                  onChange={(e) => setField("response_style", e.target.value)}
                >
                  <option value="concise">Concise</option>
                  <option value="support">Support</option>
                  <option value="sales">Sales</option>
                  <option value="formal">Formal</option>
                  <option value="detailed">Detailed</option>
                </Select>
              </Field>
              <Field label="Default language">
                <Input
                  value={form.language || "en"}
                  onChange={(e) => setField("language", e.target.value)}
                />
              </Field>
              <Field label="Supported languages (comma-separated)">
                <Input
                  value={supportedLanguagesText}
                  onChange={(e) => setSupportedLanguagesText(e.target.value)}
                />
              </Field>
            </>
          ) : null}

          {step === 2 ? (
            <>
              <Field label="Business description">
                <Input
                  value={form.business_description || ""}
                  onChange={(e) => setField("business_description", e.target.value)}
                />
              </Field>
              <Field label="Business hours summary">
                <Input
                  value={form.business_hours_summary || ""}
                  onChange={(e) =>
                    setField("business_hours_summary", e.target.value)
                  }
                />
              </Field>
              <Field label="Service areas (comma-separated)">
                <Input
                  value={serviceAreasText}
                  onChange={(e) => setServiceAreasText(e.target.value)}
                />
              </Field>
              <Field label="Booking rules">
                <Input
                  value={form.booking_rules || ""}
                  onChange={(e) => setField("booking_rules", e.target.value)}
                />
              </Field>
              <Field label="Pricing disclosure">
                <Input
                  value={form.pricing_disclosure_policy || ""}
                  onChange={(e) =>
                    setField("pricing_disclosure_policy", e.target.value)
                  }
                />
              </Field>
            </>
          ) : null}

          {step === 3 ? (
            <>
              <Field label="Handoff rules">
                <Input
                  value={form.handoff_rules_text || ""}
                  onChange={(e) => setField("handoff_rules_text", e.target.value)}
                />
              </Field>
              <Field label="Restricted topics (comma-separated)">
                <Input
                  value={restrictedTopicsText}
                  onChange={(e) => setRestrictedTopicsText(e.target.value)}
                />
              </Field>
              <Field label="Custom instructions">
                <Input
                  value={form.custom_instructions || ""}
                  onChange={(e) => setField("custom_instructions", e.target.value)}
                />
              </Field>
              <p className="text-sm text-text-muted">
                Knowledge articles can be scoped to this agent in{" "}
                <Link href="/knowledge" className="text-brand underline">
                  Knowledge
                </Link>
                .
              </p>
            </>
          ) : null}

          {step === 4 ? (
            <div className="space-y-3">
              {(
                [
                  ["crm", "CRM"],
                  ["scheduling", "Scheduling"],
                  ["knowledge", "Knowledge"],
                  ["handoff", "Human handoff"],
                  ["sms", "SMS"],
                ] as const
              ).map(([key, label]) => (
                <label
                  key={key}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
                >
                  <span className="text-sm font-medium">{label}</span>
                  <input
                    type="checkbox"
                    checked={Boolean(form.enabled_tools?.[key] ?? true)}
                    onChange={(e) =>
                      setField("enabled_tools", {
                        ...(form.enabled_tools || {}),
                        [key]: e.target.checked,
                      })
                    }
                  />
                </label>
              ))}
            </div>
          ) : null}

          {step === 5 ? (
            <div className="space-y-3">
              <p className="text-sm text-text-secondary">
                Assign numbers on the Phones page. Numbers without an explicit
                assignment use the tenant default agent.
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
              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save changes"}
              </Button>
            </div>
          </div>
        </Surface>
      </form>
    </AppShell>
  );
}

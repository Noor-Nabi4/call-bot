"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Mic } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  getAgentSettings,
  updateAgentSettings,
  type AgentSettings,
} from "@/lib/api";
import { errors, assistantSettings as copy } from "@/lib/copy";
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

const EMPTY: AgentSettings = {
  assistant_name: "",
  business_description: "",
  greeting: "",
  tone: "warm",
  response_style: "concise",
  language: "en",
  supported_languages: ["en"],
  service_areas: [],
  business_hours_summary: "",
  booking_rules: "",
  pricing_disclosure_policy: "",
  handoff_rules_text: "",
  restricted_topics: [],
  custom_instructions: "",
  profile_version: null,
  updated_at: null,
  voice: "marin",
};

function listToText(values: string[] | null | undefined): string {
  return (values || []).join(", ");
}

function textToList(value: string): string[] {
  return value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

export default function AssistantSettingsPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [form, setForm] = useState<AgentSettings>(EMPTY);
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saving, setSaving] = useState(false);
  const [supportedLanguagesText, setSupportedLanguagesText] = useState("en");
  const [serviceAreasText, setServiceAreasText] = useState("");
  const [restrictedTopicsText, setRestrictedTopicsText] = useState("");

  const load = useCallback(async () => {
    const data = await getAgentSettings();
    const settings = data.settings || EMPTY;
    setBusinessName(data.business_name || user?.tenant_name || "");
    setForm({ ...EMPTY, ...settings });
    setSupportedLanguagesText(
      listToText(settings.supported_languages?.length ? settings.supported_languages : ["en"]),
    );
    setServiceAreasText(listToText(settings.service_areas));
    setRestrictedTopicsText(listToText(settings.restricted_topics));
  }, [user?.tenant_name]);

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

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  function patch<K extends keyof AgentSettings>(key: K, value: AgentSettings[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const data = await updateAgentSettings({
        assistant_name: form.assistant_name || null,
        business_description: form.business_description || null,
        greeting: form.greeting || null,
        tone: form.tone || null,
        response_style: form.response_style || null,
        language: form.language || "en",
        supported_languages: textToList(supportedLanguagesText),
        service_areas: textToList(serviceAreasText),
        business_hours_summary: form.business_hours_summary || null,
        booking_rules: form.booking_rules || null,
        pricing_disclosure_policy: form.pricing_disclosure_policy || null,
        handoff_rules_text: form.handoff_rules_text || null,
        restricted_topics: textToList(restrictedTopicsText),
        custom_instructions: form.custom_instructions || null,
        voice: form.voice || null,
      });
      const settings = data.settings || EMPTY;
      setForm({ ...EMPTY, ...settings });
      setBusinessName(data.business_name || businessName);
      setSupportedLanguagesText(listToText(settings.supported_languages));
      setServiceAreasText(listToText(settings.service_areas));
      setRestrictedTopicsText(listToText(settings.restricted_topics));
      toast.push(copy.saved, "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader title={copy.title} description={copy.description} />

      {error ? (
        <ErrorState title={errors.loadFailed} message={error} />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={10} />
      ) : (
        <form onSubmit={onSave} className="space-y-6">
          <Surface className="space-y-4 p-5">
            <div className="flex items-center gap-2">
              <Mic className="h-4 w-4 text-muted" />
              <h2 className="text-sm font-semibold">{copy.identity}</h2>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={copy.businessName}>
                <Input value={businessName} disabled readOnly />
              </Field>
              <Field label={copy.assistantName}>
                <Input
                  value={form.assistant_name || ""}
                  onChange={(e) => patch("assistant_name", e.target.value)}
                  placeholder="Riley"
                />
              </Field>
            </div>
            <Field label={copy.businessDescription}>
              <textarea
                className="min-h-[80px] w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-sm"
                value={form.business_description || ""}
                onChange={(e) => patch("business_description", e.target.value)}
              />
            </Field>
            <Field label={copy.greeting} hint={copy.greetingHint}>
              <textarea
                className="min-h-[72px] w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-sm"
                value={form.greeting || ""}
                onChange={(e) => patch("greeting", e.target.value)}
              />
            </Field>
          </Surface>

          <Surface className="space-y-4 p-5">
            <h2 className="text-sm font-semibold">{copy.conversation}</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={copy.tone}>
                <Select
                  value={form.tone || "warm"}
                  onChange={(e) => patch("tone", e.target.value)}
                >
                  <option value="warm">Warm</option>
                  <option value="professional">Professional</option>
                  <option value="friendly">Friendly</option>
                  <option value="direct">Direct</option>
                </Select>
              </Field>
              <Field label={copy.responseStyle}>
                <Select
                  value={form.response_style || "concise"}
                  onChange={(e) => patch("response_style", e.target.value)}
                >
                  <option value="concise">Concise</option>
                  <option value="brief">Brief</option>
                  <option value="balanced">Balanced</option>
                  <option value="detailed">Detailed</option>
                </Select>
              </Field>
              <Field label={copy.defaultLanguage}>
                <Input
                  value={form.language || "en"}
                  onChange={(e) => patch("language", e.target.value)}
                  placeholder="en"
                />
              </Field>
              <Field label={copy.supportedLanguages} hint={copy.commaHint}>
                <Input
                  value={supportedLanguagesText}
                  onChange={(e) => setSupportedLanguagesText(e.target.value)}
                  placeholder="en, es"
                />
              </Field>
            </div>
          </Surface>

          <Surface className="space-y-4 p-5">
            <h2 className="text-sm font-semibold">{copy.businessRules}</h2>
            <Field label={copy.serviceAreas} hint={copy.commaHint}>
              <Input
                value={serviceAreasText}
                onChange={(e) => setServiceAreasText(e.target.value)}
                placeholder="Austin, Round Rock"
              />
            </Field>
            <Field label={copy.businessHours}>
              <Input
                value={form.business_hours_summary || ""}
                onChange={(e) =>
                  patch("business_hours_summary", e.target.value)
                }
                placeholder="Weekdays 8 AM to 6 PM"
              />
            </Field>
            <Field label={copy.bookingRules}>
              <textarea
                className="min-h-[72px] w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-sm"
                value={form.booking_rules || ""}
                onChange={(e) => patch("booking_rules", e.target.value)}
              />
            </Field>
            <Field label={copy.pricingPolicy}>
              <textarea
                className="min-h-[72px] w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-sm"
                value={form.pricing_disclosure_policy || ""}
                onChange={(e) =>
                  patch("pricing_disclosure_policy", e.target.value)
                }
              />
            </Field>
          </Surface>

          <Surface className="space-y-4 p-5">
            <h2 className="text-sm font-semibold">{copy.escalation}</h2>
            <Field label={copy.handoffRules}>
              <textarea
                className="min-h-[72px] w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-sm"
                value={form.handoff_rules_text || ""}
                onChange={(e) => patch("handoff_rules_text", e.target.value)}
              />
            </Field>
            <Field label={copy.restrictedTopics} hint={copy.commaHint}>
              <Input
                value={restrictedTopicsText}
                onChange={(e) => setRestrictedTopicsText(e.target.value)}
              />
            </Field>
          </Surface>

          <Surface className="space-y-4 p-5">
            <h2 className="text-sm font-semibold">{copy.advanced}</h2>
            <Field label={copy.customInstructions} hint={copy.customHint}>
              <textarea
                className="min-h-[100px] w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-sm"
                value={form.custom_instructions || ""}
                onChange={(e) => patch("custom_instructions", e.target.value)}
              />
            </Field>
            <div className="grid gap-4 md:grid-cols-2 text-sm text-muted">
              <div>
                {copy.profileVersion}:{" "}
                <span className="text-foreground">
                  {form.profile_version ?? "—"}
                </span>
              </div>
              <div>
                {copy.lastUpdated}:{" "}
                <span className="text-foreground">
                  {form.updated_at
                    ? new Date(form.updated_at).toLocaleString()
                    : "—"}
                </span>
              </div>
            </div>
            <p className="text-xs text-muted">{copy.noPrompt}</p>
          </Surface>

          <div className="flex justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? copy.saving : copy.save}
            </Button>
          </div>
        </form>
      )}
    </AppShell>
  );
}

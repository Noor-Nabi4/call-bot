"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { PhoneForwarded, Shield } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  Surface,
  useToast,
} from "@/components/ui";

const API_BASE =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type Settings = {
  enabled: boolean;
  mode: string;
  escalation_phone_e164: string | null;
  sip_outbound_trunk_id: string | null;
};

export default function HandoffPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const toast = useToast();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/handoff`, { credentials: "include" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setSettings(data.settings);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
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
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!settings) return;
    setError(null);
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/handoff`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSettings(data.settings);
      toast.push("Handoff rules saved", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Human handoff"
        description="Escalation rules for warm or cold SIP transfer from the voice agent."
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            load()
              .catch((e) => setError(e.message))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching || !settings ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <Surface className="p-4">
            <form onSubmit={onSave} className="space-y-4">
              <label className="flex items-start gap-3 rounded-md border border-border p-3">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={settings.enabled}
                  onChange={(e) =>
                    setSettings({ ...settings, enabled: e.target.checked })
                  }
                />
                <span>
                  <span className="block text-sm font-medium text-text-primary">
                    Enable human transfer
                  </span>
                  <span className="text-sm text-text-secondary">
                    Allow the voice agent to escalate callers to a live operator.
                  </span>
                </span>
              </label>

              <Field label="Transfer mode">
                <Select
                  value={settings.mode}
                  onChange={(e) => setSettings({ ...settings, mode: e.target.value })}
                >
                  <option value="warm">Warm (agent-assisted)</option>
                  <option value="cold">Cold (SIP REFER)</option>
                </Select>
              </Field>

              <Field
                label="Escalation phone (E.164)"
                hint="Destination number for human operators"
              >
                <Input
                  value={settings.escalation_phone_e164 || ""}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      escalation_phone_e164: e.target.value,
                    })
                  }
                  placeholder="+15551234567"
                />
              </Field>

              <Field
                label="Outbound SIP trunk ID"
                hint="Required for warm transfer via LiveKit SIP"
              >
                <Input
                  value={settings.sip_outbound_trunk_id || ""}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      sip_outbound_trunk_id: e.target.value,
                    })
                  }
                />
              </Field>

              <Button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save rules"}
              </Button>
            </form>
          </Surface>

          <aside className="space-y-3">
            <Surface className="p-4">
              <div className="flex items-center gap-2">
                <Shield className="size-4 text-brand" aria-hidden />
                <h2 className="text-sm font-semibold">Current rules</h2>
              </div>
              <dl className="mt-3 space-y-3 text-sm">
                <div>
                  <dt className="text-xs text-text-muted uppercase">Status</dt>
                  <dd className="mt-1">
                    <StatusPill status={settings.enabled ? "active" : "inactive"} />
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-text-muted uppercase">Mode</dt>
                  <dd className="mt-1">
                    <StatusPill status={settings.mode} />
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-text-muted uppercase">Escalation</dt>
                  <dd className="mt-1 font-mono text-xs">
                    {settings.escalation_phone_e164 || "Not set"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-text-muted uppercase">SIP trunk</dt>
                  <dd className="mt-1 font-mono text-xs break-all">
                    {settings.sip_outbound_trunk_id || "Not set"}
                  </dd>
                </div>
              </dl>
            </Surface>

            <Surface className="p-4 text-sm text-text-secondary">
              <div className="flex items-center gap-2 text-text-primary">
                <PhoneForwarded className="size-4" aria-hidden />
                <p className="font-medium">When handoff triggers</p>
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-4">
                <li>Agent detects caller needs a human</li>
                <li>
                  {settings.mode === "warm"
                    ? "Warm mode connects operator before releasing caller"
                    : "Cold mode transfers caller via SIP REFER"}
                </li>
                <li>
                  Calls route to{" "}
                  {settings.escalation_phone_e164 || "configured escalation number"}
                </li>
              </ul>
            </Surface>
          </aside>
        </div>
      )}
    </AppShell>
  );
}

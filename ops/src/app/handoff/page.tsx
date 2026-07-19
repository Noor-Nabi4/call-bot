"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

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
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    fetch(`${API_BASE}/api/handoff`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setSettings(d.settings))
      .catch((e) => setError(String(e)));
  }, [user]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;
  if (!settings) return <AppShell user={user}><p>Loading settings…</p></AppShell>;

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    const res = await fetch(`${API_BASE}/api/handoff`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    if (!res.ok) {
      setError(await res.text());
      return;
    }
    const data = await res.json();
    setSettings(data.settings);
    setMsg("Saved");
  }

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Human handoff</h2>
      <p className="text-sm text-ink-muted">
        Escalation phone for warm/cold SIP transfer from the voice agent.
      </p>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      {msg && <p className="mt-2 text-sm text-accent">{msg}</p>}
      <form onSubmit={onSave} className="mt-4 max-w-lg space-y-3 rounded border border-line bg-panel p-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.enabled}
            onChange={(e) =>
              setSettings({ ...settings, enabled: e.target.checked })
            }
          />
          Enable human transfer
        </label>
        <label className="block text-sm">
          Mode
          <select
            className="mt-1 w-full rounded border border-line px-2 py-1.5"
            value={settings.mode}
            onChange={(e) => setSettings({ ...settings, mode: e.target.value })}
          >
            <option value="warm">Warm (agent-assisted)</option>
            <option value="cold">Cold (SIP REFER)</option>
          </select>
        </label>
        <label className="block text-sm">
          Escalation phone (E.164)
          <input
            className="mt-1 w-full rounded border border-line px-2 py-1.5"
            value={settings.escalation_phone_e164 || ""}
            onChange={(e) =>
              setSettings({
                ...settings,
                escalation_phone_e164: e.target.value,
              })
            }
            placeholder="+15551234567"
          />
        </label>
        <label className="block text-sm">
          Outbound SIP trunk ID (warm)
          <input
            className="mt-1 w-full rounded border border-line px-2 py-1.5"
            value={settings.sip_outbound_trunk_id || ""}
            onChange={(e) =>
              setSettings({
                ...settings,
                sip_outbound_trunk_id: e.target.value,
              })
            }
          />
        </label>
        <button
          type="submit"
          className="rounded bg-accent px-3 py-1.5 text-sm text-white"
        >
          Save
        </button>
      </form>
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Bot, Plus, Sparkles, Star } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  createAgentProfile,
  listAgentProfiles,
  listIndustryTemplates,
  setDefaultAgentProfile,
  type AgentProfile,
  type IndustryTemplate,
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

export default function AgentsPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [industryKey, setIndustryKey] = useState("custom");
  const [agentType, setAgentType] = useState("receptionist");

  const load = useCallback(async () => {
    const [profileData, templateData] = await Promise.all([
      listAgentProfiles(),
      listIndustryTemplates(),
    ]);
    setProfiles(profileData.profiles);
    setBusinessName(profileData.business_name || user?.tenant_name || "");
    setTemplates(templateData.templates);
  }, [user?.tenant_name]);

  useEffect(() => {
    if (!user) return;
    setFetching(true);
    load()
      .catch((err) => setError(safeUserError(err, "Could not load agents")))
      .finally(() => setFetching(false));
  }, [user, load]);

  async function onCreate() {
    if (!name.trim()) {
      toast.push("Name is required", "error");
      return;
    }
    setCreating(true);
    try {
      const created = await createAgentProfile({
        name: name.trim(),
        agent_type: agentType,
        industry_key: industryKey === "custom" ? null : industryKey,
        is_default: profiles.length === 0,
      });
      toast.push("Agent created", "success");
      setName("");
      await load();
      window.location.assign(`/agents/${created.profile.id}`);
    } catch (err) {
      toast.push(safeUserError(err, "Could not create agent"), "error");
    } finally {
      setCreating(false);
    }
  }

  async function onSetDefault(id: string) {
    try {
      await setDefaultAgentProfile(id);
      toast.push("Default agent updated", "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Could not set default"), "error");
    }
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Agents"
        description={`Configure AI employees for ${businessName || "your business"}. Each profile has its own voice, tools, and phone routing.`}
        actions={
          <Link href="/phones">
            <Button variant="secondary" size="sm">
              Manage phones
            </Button>
          </Link>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Surface className="ops-surface-rise p-5">
          <div className="mb-4 flex items-center gap-2">
            <Bot className="size-4 text-brand" aria-hidden />
            <h2 className="font-heading text-lg font-semibold">Profiles</h2>
          </div>
          {fetching ? (
            <LoadingSkeleton rows={4} />
          ) : profiles.length === 0 ? (
            <p className="text-sm text-text-muted">
              No agents yet. Create one from an industry template to get started.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {profiles.map((profile) => (
                <li
                  key={profile.id}
                  className="flex flex-wrap items-center justify-between gap-3 py-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link
                        href={`/agents/${profile.id}`}
                        className="font-medium text-text-primary hover:text-brand"
                      >
                        {profile.name}
                      </Link>
                      {profile.is_default ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-brand">
                          <Star className="size-3" aria-hidden />
                          Default
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-xs text-text-muted">
                      {profile.agent_type}
                      {profile.industry_key ? ` · ${profile.industry_key}` : ""}
                      {profile.greeting ? ` · ${profile.greeting.slice(0, 60)}` : ""}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {!profile.is_default ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => onSetDefault(profile.id)}
                      >
                        Set default
                      </Button>
                    ) : null}
                    <Link href={`/agents/${profile.id}`}>
                      <Button size="sm">Open builder</Button>
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Surface>

        <Surface className="ops-surface-rise p-5">
          <div className="mb-4 flex items-center gap-2">
            <Sparkles className="size-4 text-brand" aria-hidden />
            <h2 className="font-heading text-lg font-semibold">New agent</h2>
          </div>
          <div className="space-y-3">
            <Field label="Name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Main Receptionist"
              />
            </Field>
            <Field label="Industry template">
              <Select
                value={industryKey}
                onChange={(e) => {
                  setIndustryKey(e.target.value);
                  const tpl = templates.find((t) => t.key === e.target.value);
                  if (tpl) setAgentType(tpl.agent_type);
                }}
              >
                {templates.map((tpl) => (
                  <option key={tpl.key} value={tpl.key}>
                    {tpl.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Agent type">
              <Select value={agentType} onChange={(e) => setAgentType(e.target.value)}>
                <option value="receptionist">Receptionist</option>
                <option value="support">Support</option>
                <option value="sales">Sales</option>
                <option value="booking">Booking</option>
                <option value="help_desk">Help desk</option>
                <option value="call_center">Call center</option>
                <option value="custom">Custom</option>
              </Select>
            </Field>
            <Button onClick={onCreate} disabled={creating} className="w-full">
              <Plus className="size-3.5" aria-hidden />
              {creating ? "Creating…" : "Create agent"}
            </Button>
          </div>
        </Surface>
      </div>
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Bot, Plus, Star } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  createAgentProfile,
  archiveAgentProfile,
  listAgentProfiles,
  listIndustryTemplates,
  setDefaultAgentProfile,
  type AgentProfile,
  type IndustryTemplate,
} from "@/lib/api";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ConfirmDialog,
  DetailDrawer,
  EmptyState,
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

const CREATE_FORM_ID = "create-agent-form";

export default function AgentsPage() {
  const { user, loading, forbidden } = useAuth({ permission: "agents.manage" });
  const toast = useToast();
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [businessName, setBusinessName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [industryKey, setIndustryKey] = useState("custom");
  const [agentType, setAgentType] = useState("receptionist");
  const [archiveTarget, setArchiveTarget] = useState<AgentProfile | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);

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
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((err) => setError(safeUserError(err, "Could not load agents")))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  function closeCreate() {
    if (creating) return;
    setCreateOpen(false);
    setName("");
    setIndustryKey("custom");
    setAgentType("receptionist");
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
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
      setCreateOpen(false);
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

  async function onConfirmArchive() {
    if (!archiveTarget) return;
    setArchiveBusy(true);
    try {
      await archiveAgentProfile(archiveTarget.id);
      toast.push("Agent archived", "success");
      setArchiveTarget(null);
      await load();
    } catch (err) {
      toast.push(safeUserError(err, "Could not archive agent"), "error");
    } finally {
      setArchiveBusy(false);
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

  return (
    <AppShell user={user}>
      <PageHeader
        title="Agents"
        description={`Configure AI employees for ${businessName || "your business"}. Each profile has its own voice, tools, and phone routing.`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/phones">
              <Button variant="secondary" size="sm">
                Manage phones
              </Button>
            </Link>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-3.5" aria-hidden />
              Create agent
            </Button>
          </div>
        }
      />

      {error ? <ErrorState message={error} onRetry={() => load()} /> : null}

      {fetching ? (
        <LoadingSkeleton rows={4} />
      ) : profiles.length === 0 ? (
        <EmptyState
          icon={<Bot className="size-8" />}
          title="No agents yet"
          description="Create one from an industry template to get started."
          action={
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-3.5" aria-hidden />
              Create agent
            </Button>
          }
        />
      ) : (
        <Surface className="ops-surface-rise p-5">
          <div className="mb-4 flex items-center gap-2">
            <Bot className="size-4 text-brand" aria-hidden />
            <h2 className="font-heading text-lg font-semibold">Profiles</h2>
          </div>
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
                    {profile.greeting
                      ? ` · ${profile.greeting.slice(0, 60)}`
                      : ""}
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
                  {!profile.is_default ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-danger"
                      onClick={() => setArchiveTarget(profile)}
                    >
                      Archive
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </Surface>
      )}

      <DetailDrawer
        open={createOpen}
        onClose={closeCreate}
        title="Create agent"
        description="Start from an industry template or build a custom profile."
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={closeCreate}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button
              form={CREATE_FORM_ID}
              type="submit"
              disabled={creating || !name.trim()}
            >
              {creating ? "Creating…" : "Create agent"}
            </Button>
          </div>
        }
      >
        <form id={CREATE_FORM_ID} onSubmit={onCreate} className="grid gap-3">
          <Field label="Name">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Main Receptionist"
              required
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
            <Select
              value={agentType}
              onChange={(e) => setAgentType(e.target.value)}
            >
              <option value="receptionist">Receptionist</option>
              <option value="support">Support</option>
              <option value="sales">Sales</option>
              <option value="booking">Booking</option>
              <option value="help_desk">Help desk</option>
              <option value="call_center">Call center</option>
              <option value="custom">Custom</option>
            </Select>
          </Field>
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={!!archiveTarget}
        title="Archive agent?"
        description={
          archiveTarget
            ? `${archiveTarget.name} will be archived and hidden from the active list. Phone routing should be reassigned first if this agent still owns numbers.`
            : undefined
        }
        confirmLabel="Archive"
        danger
        busy={archiveBusy}
        onConfirm={() => {
          void onConfirmArchive();
        }}
        onCancel={() => {
          if (archiveBusy) return;
          setArchiveTarget(null);
        }}
      />
    </AppShell>
  );
}

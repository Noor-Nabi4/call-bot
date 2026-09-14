"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, Zap } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, automations as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ConfirmDialog,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Surface,
  Textarea,
  useToast,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const CREATE_FORM_ID = "create-automation-form";

type CatalogItem = { key: string; label: string; description: string };
type Rule = {
  id: string;
  name: string;
  description: string | null;
  trigger_key: string;
  action_key: string;
  config: {
    service_type?: string;
    url?: string;
    secret?: string;
    timeout_sec?: number;
  };
  is_enabled: boolean;
};

const EMPTY_FORM = {
  name: "",
  description: "",
  trigger_key: "call.handoff_requested",
  action_key: "write_audit",
  service_type: "Handoff follow-up",
  webhook_url: "",
  webhook_secret: "",
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let message: string = errors.generic;
    try {
      const body = (await res.json()) as {
        detail?: { message?: string } | string;
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      /* keep generic */
    }
    throw new Error(message);
  }
  return res.json();
}

export default function AutomationsPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [rules, setRules] = useState<Rule[]>([]);
  const [triggers, setTriggers] = useState<CatalogItem[]>([]);
  const [actions, setActions] = useState<CatalogItem[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Rule | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  function buildConfig() {
    if (form.action_key === "create_follow_up_job") {
      return { service_type: form.service_type || "Automated follow-up" };
    }
    if (form.action_key === "post_webhook") {
      return {
        url: form.webhook_url.trim(),
        secret: form.webhook_secret.trim() || null,
      };
    }
    return {};
  }

  const refresh = useCallback(async () => {
    const data = await api<{
      rules: Rule[];
      catalog: { triggers: CatalogItem[]; actions: CatalogItem[] };
    }>("/api/admin/automations");
    setRules(data.rules || []);
    setTriggers(data.catalog?.triggers || []);
    setActions(data.catalog?.actions || []);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refresh()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, refresh]);

  function closeCreate() {
    if (busy) return;
    setCreateOpen(false);
    setForm(EMPTY_FORM);
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/admin/automations", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          trigger_key: form.trigger_key,
          action_key: form.action_key,
          config: buildConfig(),
          is_enabled: true,
        }),
      });
      setForm(EMPTY_FORM);
      setCreateOpen(false);
      toast.push(copy.created, "success");
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setBusy(false);
    }
  }

  async function onToggle(rule: Rule) {
    setError(null);
    try {
      await api(`/api/admin/automations/${rule.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_enabled: !rule.is_enabled }),
      });
      toast.push(rule.is_enabled ? copy.disabled : copy.enabled, "success");
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    }
  }

  async function onConfirmDelete() {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    setError(null);
    try {
      await api(`/api/admin/automations/${deleteTarget.id}`, {
        method: "DELETE",
      });
      toast.push(copy.deleted, "success");
      setDeleteTarget(null);
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.deleteFailed));
    } finally {
      setDeleteBusy(false);
    }
  }

  const labelFor = (items: CatalogItem[], key: string) =>
    items.find((i) => i.key === key)?.label || key;

  if (loading || !user) {
    return <LoadingSkeleton rows={6} />;
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="size-3.5" aria-hidden />
            {copy.create}
          </Button>
        }
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => setError(null)}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : rules.length === 0 ? (
        <EmptyState
          icon={<Zap className="size-8" />}
          title={copy.empty}
          description={copy.emptyHint}
          action={
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="size-3.5" aria-hidden />
              {copy.create}
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <Surface key={rule.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="m-0 text-sm font-semibold text-ink">
                    {rule.name}
                  </h3>
                  <p className="mt-1 m-0 text-xs text-text-muted">
                    {labelFor(triggers, rule.trigger_key)} →{" "}
                    {labelFor(actions, rule.action_key)}
                    {rule.is_enabled ? "" : ` · ${copy.inactive}`}
                  </p>
                  {rule.description ? (
                    <p className="mt-2 m-0 text-sm text-text-secondary">
                      {rule.description}
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onToggle(rule)}
                  >
                    {rule.is_enabled ? copy.disable : copy.enable}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-danger"
                    onClick={() => setDeleteTarget(rule)}
                  >
                    {copy.delete}
                  </Button>
                </div>
              </div>
            </Surface>
          ))}
        </div>
      )}

      <DetailDrawer
        open={createOpen}
        onClose={closeCreate}
        title={copy.create}
        description={copy.createHint}
        width="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeCreate} disabled={busy}>
              Cancel
            </Button>
            <Button form={CREATE_FORM_ID} type="submit" disabled={busy}>
              {busy ? copy.saving : copy.createAction}
            </Button>
          </div>
        }
      >
        <form id={CREATE_FORM_ID} onSubmit={onCreate} className="grid gap-3">
          <Field label="Name">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </Field>
          <Field label="Description">
            <Textarea
              rows={2}
              value={form.description}
              onChange={(e) =>
                setForm({ ...form, description: e.target.value })
              }
            />
          </Field>
          <Field label="Trigger">
            <Select
              value={form.trigger_key}
              onChange={(e) =>
                setForm({ ...form, trigger_key: e.target.value })
              }
            >
              {triggers.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Action">
            <Select
              value={form.action_key}
              onChange={(e) =>
                setForm({ ...form, action_key: e.target.value })
              }
            >
              {actions.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.label}
                </option>
              ))}
            </Select>
          </Field>
          {form.action_key === "create_follow_up_job" ? (
            <Field label="Job service type">
              <Input
                value={form.service_type}
                onChange={(e) =>
                  setForm({ ...form, service_type: e.target.value })
                }
              />
            </Field>
          ) : null}
          {form.action_key === "post_webhook" ? (
            <>
              <Field label="HTTPS webhook URL">
                <Input
                  value={form.webhook_url}
                  onChange={(e) =>
                    setForm({ ...form, webhook_url: e.target.value })
                  }
                  placeholder="https://example.com/hooks/voxpilot"
                  required
                />
              </Field>
              <Field label="Shared secret (optional)">
                <Input
                  type="password"
                  value={form.webhook_secret}
                  onChange={(e) =>
                    setForm({ ...form, webhook_secret: e.target.value })
                  }
                  placeholder="Used for X-VoxPilot-Signature"
                />
              </Field>
            </>
          ) : null}
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={!!deleteTarget}
        title={copy.deleteTitle}
        description={copy.deleteBody.replace(
          "{name}",
          deleteTarget?.name || "this rule",
        )}
        confirmLabel={copy.delete}
        danger
        busy={deleteBusy}
        onConfirm={() => {
          void onConfirmDelete();
        }}
        onCancel={() => {
          if (deleteBusy) return;
          setDeleteTarget(null);
        }}
      />
    </AppShell>
  );
}

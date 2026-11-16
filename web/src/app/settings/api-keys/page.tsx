"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound, Plus } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, apiKeys as copy } from "@/lib/ops-copy";
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
  Surface,
  useToast,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const CREATE_FORM_ID = "create-api-key-form";

type ApiKey = {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  created_at?: string | null;
  secret?: string;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(errors.loadFailed);
  return res.json();
}

export default function ApiKeysPage() {
  const { user, loading, forbidden } = useAuth({ permission: "api_keys.manage" });
  const toast = useToast();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [scopes, setScopes] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [fetching, setFetching] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null);
  const [revokeBusy, setRevokeBusy] = useState(false);

  const load = useCallback(async () => {
    const data = await api<{ keys: ApiKey[]; available_scopes: string[] }>(
      "/api/admin/api-keys",
    );
    setKeys(data.keys || []);
    setScopes(data.available_scopes || []);
  }, []);

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

  function closeCreate() {
    if (busy) return;
    setCreateOpen(false);
    setName("");
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await api<{ key: ApiKey }>("/api/admin/api-keys", {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), scopes }),
      });
      setRevealed(data.key.secret || null);
      setName("");
      setCreateOpen(false);
      toast.push(copy.created, "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmRevoke() {
    if (!revokeTarget) return;
    setRevokeBusy(true);
    try {
      await api(`/api/admin/api-keys/${revokeTarget.id}`, { method: "DELETE" });
      toast.push(copy.revoked, "success");
      setRevokeTarget(null);
      await load();
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setRevokeBusy(false);
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
          onRetry={() => void load()}
        />
      ) : null}

      {revealed ? (
        <Surface className="mb-4 border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-text-primary">
            {copy.secretOnce}
          </p>
          <p className="mt-2 break-all font-mono text-sm">{revealed}</p>
          <Button
            className="mt-3"
            size="sm"
            variant="secondary"
            onClick={() => setRevealed(null)}
          >
            {copy.dismissSecret}
          </Button>
        </Surface>
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={4} />
      ) : keys.length === 0 ? (
        <EmptyState
          icon={<KeyRound className="size-8" />}
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
          {keys.map((key) => (
            <Surface key={key.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold">{key.name}</h3>
                  <p className="mt-1 font-mono text-xs text-text-secondary">
                    {key.key_prefix}…
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {key.is_active ? copy.active : copy.inactive} ·{" "}
                    {key.scopes.join(", ")}
                  </p>
                </div>
                {key.is_active ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-danger"
                    disabled={revokeBusy}
                    onClick={() => setRevokeTarget(key)}
                  >
                    {copy.revoke}
                  </Button>
                ) : null}
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
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeCreate} disabled={busy}>
              Cancel
            </Button>
            <Button
              form={CREATE_FORM_ID}
              type="submit"
              disabled={busy || !name.trim()}
            >
              {busy ? copy.creating : copy.create}
            </Button>
          </div>
        }
      >
        <form id={CREATE_FORM_ID} onSubmit={onCreate} className="grid gap-3">
          <Field label={copy.name}>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </Field>
          <p className="text-xs text-text-muted">
            {copy.scopesHint}: {scopes.join(", ") || "—"}
          </p>
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={!!revokeTarget}
        title={copy.revokeTitle}
        description={copy.revokeBody.replace(
          "{name}",
          revokeTarget?.name || "this key",
        )}
        confirmLabel={copy.revoke}
        danger
        busy={revokeBusy}
        onConfirm={() => {
          void onConfirmRevoke();
        }}
        onCancel={() => {
          if (revokeBusy) return;
          setRevokeTarget(null);
        }}
      />
    </AppShell>
  );
}

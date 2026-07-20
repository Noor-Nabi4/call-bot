"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { KeyRound } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, apiKeys as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  EmptyState,
  ErrorState,
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
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [scopes, setScopes] = useState<string[]>([]);
  const [name, setName] = useState("");
  const [fetching, setFetching] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<string | null>(null);

  const load = useCallback(async () => {
    const data = await api<{ keys: ApiKey[]; available_scopes: string[] }>(
      "/api/admin/api-keys",
    );
    setKeys(data.keys || []);
    setScopes(data.available_scopes || []);
  }, []);

  useEffect(() => {
    if (!user) return;
    load()
      .catch((e) => setError(safeUserError(e, errors.loadFailed)))
      .finally(() => setFetching(false));
  }, [user, load]);

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
      toast.push(copy.created, "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    setBusy(true);
    try {
      await api(`/api/admin/api-keys/${id}`, { method: "DELETE" });
      toast.push(copy.revoked, "success");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setBusy(false);
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
      <PageHeader title={copy.title} description={copy.description} />

      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}

      {revealed ? (
        <Surface className="mb-4 border-amber-300 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-text-primary">{copy.secretOnce}</p>
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

      <div className="grid gap-4 lg:grid-cols-2">
        <Surface className="p-4">
          <h2 className="text-sm font-semibold">{copy.create}</h2>
          <form onSubmit={onCreate} className="mt-3 grid gap-3">
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
            <Button type="submit" disabled={busy || !name.trim()} className="w-fit">
              {busy ? copy.creating : copy.create}
            </Button>
          </form>
        </Surface>

        <div className="space-y-3">
          {fetching ? <LoadingSkeleton rows={4} /> : null}
          {!fetching && keys.length === 0 ? (
            <EmptyState
              icon={<KeyRound className="size-8" />}
              title={copy.empty}
              description={copy.emptyHint}
            />
          ) : null}
          {keys.map((key) => (
            <Surface key={key.id} className="p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
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
                    disabled={busy}
                    onClick={() => void onRevoke(key.id)}
                  >
                    {copy.revoke}
                  </Button>
                ) : null}
              </div>
            </Surface>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

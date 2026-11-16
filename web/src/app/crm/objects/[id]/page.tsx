"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import { DynamicForm, type CrmFieldDef } from "@/components/crm/FieldRenderer";
import { useAuth } from "@/lib/use-auth";
import { hasPermission } from "@/lib/permissions";
import {
  Button,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type RecordRow = {
  id: string;
  values: Record<string, unknown>;
  archived_at?: string | null;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let message = "Request failed";
    try {
      const body = await res.json();
      message = body?.detail?.message || body?.detail || message;
    } catch {
      /* ignore */
    }
    throw new Error(typeof message === "string" ? message : "Request failed");
  }
  return res.json();
}

export default function CustomObjectPage() {
  const params = useParams<{ id?: string }>();
  const objectId = String(params.id || "");
  const { user, loading: authLoading } = useAuth({
    permission: "custom_objects.read",
  });
  const toast = useToast();
  const [fields, setFields] = useState<CrmFieldDef[]>([]);
  const [items, setItems] = useState<RecordRow[]>([]);
  const [objectName, setObjectName] = useState("Custom object");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!objectId) return;
    setLoading(true);
    setError(null);
    try {
      const body = await api<{
        object: { name: string; plural_name?: string };
        fields: CrmFieldDef[];
        items: RecordRow[];
      }>(`/api/admin/crm/objects/${objectId}/records`);
      setObjectName(body.object.plural_name || body.object.name);
      setFields(body.fields || []);
      setItems(body.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [objectId]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  if (authLoading || !user) {
    return <LoadingSkeleton rows={6} />;
  }
  if (!hasPermission(user, "custom_objects.read")) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  const canManage = hasPermission(user, "custom_objects.manage");

  return (
    <AppShell user={user}>
      <PageHeader title={objectName} description="Custom object records" />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading ? <LoadingSkeleton rows={6} /> : null}
      {!loading && !error ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Surface className="p-4">
            <h2 className="mb-3 text-sm font-semibold text-text-primary">Records</h2>
            <ul className="divide-y divide-border">
              {items.length === 0 ? (
                <li className="py-3 text-sm text-text-muted">No records yet.</li>
              ) : (
                items.map((row) => (
                  <li key={row.id} className="py-3 text-sm">
                    <code className="text-xs text-text-muted">{row.id.slice(0, 8)}</code>
                    <pre className="mt-1 overflow-x-auto text-xs text-text-primary">
                      {JSON.stringify(row.values, null, 2)}
                    </pre>
                  </li>
                ))
              )}
            </ul>
          </Surface>
          {canManage ? (
            <Surface className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-text-primary">New record</h2>
              <DynamicForm
                fields={fields}
                values={values}
                onChange={(key, value) =>
                  setValues((prev) => ({ ...prev, [key]: value }))
                }
              />
              <div className="mt-4">
                <Button
                  onClick={async () => {
                    try {
                      await api(`/api/admin/crm/objects/${objectId}/records`, {
                        method: "POST",
                        body: JSON.stringify({ values }),
                      });
                      setValues({});
                      toast.push("Record created", "success");
                      await load();
                    } catch (err) {
                      toast.push(
                        err instanceof Error ? err.message : "Create failed",
                        "error",
                      );
                    }
                  }}
                >
                  Create
                </Button>
              </div>
            </Surface>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}

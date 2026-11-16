"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
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

type ModuleRow = {
  key: string;
  name: string;
  enabled: boolean;
  display_order: number;
  required?: boolean;
  ui_live?: boolean;
  description?: string;
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

export default function CrmModulesSettingsPage() {
  const { user, loading: authLoading } = useAuth({
    permission: "organization.read",
  });
  const toast = useToast();
  const [modules, setModules] = useState<ModuleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await api<{ modules: ModuleRow[] }>("/api/admin/crm/modules");
      setModules(body.modules);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load modules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  if (authLoading || !user) {
    return <LoadingSkeleton rows={6} />;
  }
  if (!hasPermission(user, "crm.configure") && !hasPermission(user, "organization.read")) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  const canConfigure = hasPermission(user, "crm.configure");

  return (
    <AppShell user={user}>
      <PageHeader
        title="CRM modules"
        description="Enable or disable modules for this organization. Only modules with a live workspace page can be turned on. Disabling hides navigation without deleting data."
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading ? <LoadingSkeleton rows={8} /> : null}
      {!loading && !error ? (
        <Surface className="divide-y divide-border">
          {modules.map((mod) => {
            const live = mod.ui_live === true;
            const canToggle =
              canConfigure &&
              live &&
              !(mod.required && mod.enabled) &&
              busy !== mod.key;
            return (
            <div
              key={mod.key}
              className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
            >
              <div>
                <p className="font-medium text-text-primary">{mod.name}</p>
                <p className="text-sm text-text-muted">
                  {mod.key}
                  {mod.required ? " · required" : ""}
                  {!live ? " · not available yet" : ""}
                  {mod.description ? ` — ${mod.description}` : ""}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">
                  {!live
                    ? "Unavailable"
                    : mod.enabled
                      ? "Enabled"
                      : "Disabled"}
                </span>
                {canConfigure ? (
                  <Button
                    size="sm"
                    variant={mod.enabled ? "secondary" : "primary"}
                    disabled={!canToggle}
                    onClick={async () => {
                      setBusy(mod.key);
                      try {
                        await api(`/api/admin/crm/modules/${mod.key}`, {
                          method: "PATCH",
                          body: JSON.stringify({ enabled: !mod.enabled }),
                        });
                        toast.push(
                          mod.enabled ? "Module disabled" : "Module enabled",
                          "success",
                        );
                        await load();
                      } catch (err) {
                        toast.push(
                          err instanceof Error ? err.message : "Update failed",
                          "error",
                        );
                      } finally {
                        setBusy(null);
                      }
                    }}
                  >
                    {mod.enabled ? "Disable" : "Enable"}
                  </Button>
                ) : null}
              </div>
            </div>
            );
          })}
        </Surface>
      ) : null}
    </AppShell>
  );
}

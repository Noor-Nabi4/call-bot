"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Shield } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  createOrgRole,
  getOrgRole,
  listOrgRoles,
  listPlatformPermissions,
  updateOrgRole,
  type OrgRole,
  type PlatformPermission,
} from "@/lib/api/admin";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  ForbiddenState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
  type DataTableColumn,
} from "@/components/ui";

export default function RolesPage() {
  const { user, loading, forbidden } = useAuth({ permission: "roles.read" });
  const toast = useToast();
  const [roles, setRoles] = useState<OrgRole[]>([]);
  const [catalog, setCatalog] = useState<PlatformPermission[]>([]);
  const [selected, setSelected] = useState<OrgRole | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDesc, setCreateDesc] = useState("");

  const refresh = useCallback(async () => {
    const [r, p] = await Promise.all([listOrgRoles(), listPlatformPermissions()]);
    setRoles(r.roles || []);
    setCatalog(p.permissions || []);
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

  async function openRole(role: OrgRole) {
    setBusy(true);
    setError(null);
    try {
      const detail = await getOrgRole(role.id);
      setSelected(detail.role);
      setSelectedKeys(
        new Set((detail.role.permissions || []).map((p) => p.key)),
      );
    } catch (err) {
      setError(safeUserError(err, errors.loadFailed));
    } finally {
      setBusy(false);
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await createOrgRole({
        name: createName,
        description: createDesc || undefined,
        permissions: [],
      });
      setCreateName("");
      setCreateDesc("");
      toast.push("Role created", "success");
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setBusy(false);
    }
  }

  async function onSavePermissions() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await updateOrgRole(selected.id, {
        permissions: Array.from(selectedKeys).map((key) => ({
          key,
          scope: "ALL_ORGANIZATION",
        })),
      });
      toast.push("Permissions saved", "success");
      await refresh();
      await openRole(selected);
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setBusy(false);
    }
  }

  const columns: DataTableColumn<OrgRole>[] = [
    {
      id: "name",
      header: "Role",
      cell: (r) => (
        <button
          type="button"
          className="font-medium text-left text-accent hover:underline"
          onClick={() => openRole(r)}
        >
          {r.name}
        </button>
      ),
    },
    {
      id: "type",
      header: "Type",
      cell: (r) => (r.is_system ? "System" : "Custom"),
      className: "w-28",
    },
    {
      id: "status",
      header: "Status",
      cell: (r) => (r.is_active ? "active" : "inactive"),
      className: "w-24",
    },
  ];

  if (loading || !user) {
    return <LoadingSkeleton rows={4} />;
  }

  if (forbidden && user) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Roles & permissions"
        description="Organization roles use platform-defined permissions. Owner is protected."
        actions={
          <Link
            href="/settings/team"
            className="text-sm text-accent hover:underline"
          >
            Back to team
          </Link>
        }
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <Surface className="p-4">
              <div className="mb-3 flex items-center gap-2">
                <Shield className="size-4 text-text-muted" aria-hidden />
                <h2 className="text-sm font-semibold">Roles</h2>
              </div>
              {roles.length === 0 ? (
                <EmptyState title="No roles" description="System roles will appear after first admin." />
              ) : (
                <DataTable columns={columns} rows={roles} />
              )}
            </Surface>

            <Surface className="p-4">
              <h2 className="mb-3 text-sm font-semibold">Create custom role</h2>
              <form onSubmit={onCreate} className="space-y-3">
                <Field label="Name">
                  <Input
                    value={createName}
                    onChange={(e) => setCreateName(e.target.value)}
                    required
                    maxLength={128}
                  />
                </Field>
                <Field label="Description">
                  <Input
                    value={createDesc}
                    onChange={(e) => setCreateDesc(e.target.value)}
                    maxLength={500}
                  />
                </Field>
                <Button type="submit" disabled={busy || !createName.trim()}>
                  Create role
                </Button>
              </form>
            </Surface>
          </div>

          <Surface className="p-4">
            {!selected ? (
              <EmptyState
                title="Select a role"
                description="Choose a role to view or edit its permissions."
              />
            ) : (
              <div className="space-y-3">
                <h2 className="text-sm font-semibold">{selected.name}</h2>
                <p className="text-sm text-text-secondary">
                  {selected.description ||
                    (selected.is_system
                      ? "System role"
                      : "Custom organization role")}
                </p>
                {selected.name === "Owner" ? (
                  <p className="text-sm text-text-muted">
                    Owner permissions are fixed and cannot be edited.
                  </p>
                ) : (
                  <>
                    <div className="max-h-96 space-y-1 overflow-y-auto rounded-md border border-border p-2">
                      {catalog.map((p) => (
                        <label
                          key={p.key}
                          className="flex items-start gap-2 rounded px-2 py-1 text-sm hover:bg-surface-muted"
                        >
                          <input
                            type="checkbox"
                            className="mt-1"
                            checked={selectedKeys.has(p.key)}
                            disabled={busy || selected.name === "Owner"}
                            onChange={(e) => {
                              const next = new Set(selectedKeys);
                              if (e.target.checked) next.add(p.key);
                              else next.delete(p.key);
                              setSelectedKeys(next);
                            }}
                          />
                          <span>
                            <span className="font-mono text-xs">{p.key}</span>
                            <span className="block text-text-secondary">
                              {p.description}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                    <Button
                      type="button"
                      disabled={busy || selected.name === "Owner"}
                      onClick={onSavePermissions}
                    >
                      Save permissions
                    </Button>
                  </>
                )}
              </div>
            )}
          </Surface>
        </div>
      )}
    </AppShell>
  );
}

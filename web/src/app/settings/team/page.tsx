"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, UserPlus } from "lucide-react";
import { AppShell } from "@/components/shell";
import { UsageSummaryPanel, seatsAtLimit } from "@/components/ops";
import { useAuth } from "@/lib/use-auth";
import { errors, team as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  inviteTeamUser,
  listTeamUsers,
  updateTeamUser,
  type TeamUser,
} from "@/lib/api/admin";
import { getUsage, type TenantUsage } from "@/lib/api";
import {
  Button,
  ConfirmDialog,
  DataTable,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  useToast,
  type DataTableColumn,
} from "@/components/ui";

const EMPTY_INVITE = {
  name: "",
  email: "",
  password: "",
  role: "dispatcher",
};

const INVITE_FORM_ID = "invite-teammate-form";

export default function TeamPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [users, setUsers] = useState<TeamUser[]>([]);
  const [usage, setUsage] = useState<TenantUsage | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteBusy, setInviteBusy] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);
  const [invite, setInvite] = useState(EMPTY_INVITE);
  const [confirmTarget, setConfirmTarget] = useState<TeamUser | null>(null);

  const refresh = useCallback(async () => {
    const [teamData, usageData] = await Promise.all([
      listTeamUsers(),
      getUsage(),
    ]);
    setUsers(teamData.users || []);
    setUsage(usageData.usage);
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

  const atSeatLimit = seatsAtLimit(usage);

  function openInvite() {
    if (atSeatLimit) {
      toast.push(copy.seatLimitReached, "error");
      return;
    }
    setInviteOpen(true);
  }

  function closeInvite() {
    if (inviteBusy) return;
    setInviteOpen(false);
    setInvite(EMPTY_INVITE);
  }

  async function onInvite(e: FormEvent) {
    e.preventDefault();
    if (atSeatLimit) {
      toast.push(copy.seatLimitReached, "error");
      return;
    }
    setInviteBusy(true);
    setError(null);
    try {
      await inviteTeamUser(invite);
      setInvite(EMPTY_INVITE);
      setInviteOpen(false);
      toast.push(copy.invited, "success");
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.createFailed));
    } finally {
      setInviteBusy(false);
    }
  }

  async function onRoleChange(target: TeamUser, role: string) {
    if (role === target.role) return;
    setRowBusy(target.id);
    setError(null);
    try {
      await updateTeamUser(target.id, { role });
      toast.push(copy.updated, "success");
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setRowBusy(null);
    }
  }

  async function onConfirmToggleActive() {
    if (!confirmTarget) return;
    const target = confirmTarget;
    setRowBusy(target.id);
    setError(null);
    try {
      await updateTeamUser(target.id, { is_active: !target.is_active });
      toast.push(
        target.is_active ? copy.deactivated : copy.reactivated,
        "success",
      );
      setConfirmTarget(null);
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setRowBusy(null);
    }
  }

  const columns: DataTableColumn<TeamUser>[] = [
    {
      id: "name",
      header: "Name",
      cell: (u) => <span className="font-medium">{u.name}</span>,
    },
    {
      id: "email",
      header: "Email",
      cell: (u) => <span className="text-text-secondary">{u.email}</span>,
    },
    {
      id: "role",
      header: "Role",
      cell: (u) => (
        <Select
          value={u.role}
          disabled={rowBusy === u.id || u.id === user?.id}
          onChange={(e) => onRoleChange(u, e.target.value)}
          className="max-w-[9rem]"
        >
          <option value="admin">admin</option>
          <option value="dispatcher">dispatcher</option>
          <option value="technician">technician</option>
        </Select>
      ),
      className: "w-36",
    },
    {
      id: "status",
      header: "Status",
      cell: (u) => (
        <span
          className={
            u.is_active
              ? "font-mono text-xs uppercase text-success"
              : "font-mono text-xs uppercase text-text-muted"
          }
        >
          {u.status ?? (u.is_active ? "active" : "inactive")}
        </span>
      ),
      className: "w-24",
    },
    {
      id: "actions",
      header: "",
      cell: (u) => (
        <Button
          size="sm"
          variant={u.is_active ? "danger" : "secondary"}
          disabled={rowBusy === u.id || u.id === user?.id}
          onClick={() => setConfirmTarget(u)}
        >
          {u.is_active ? copy.deactivate : copy.reactivate}
        </Button>
      ),
      className: "w-36",
    },
  ];

  if (loading || !user) {
    return <LoadingSkeleton rows={6} />;
  }

  const confirmingDeactivate = Boolean(confirmTarget?.is_active);

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <Button size="sm" onClick={openInvite} disabled={atSeatLimit}>
            <Plus className="size-3.5" aria-hidden />
            {copy.invite}
          </Button>
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

      {usage ? (
        <UsageSummaryPanel
          usage={usage}
          compact
          showBillingLink
          className="mb-4"
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <DataTable
          columns={columns}
          rows={users}
          empty={
            <EmptyState
              title={copy.noUsers}
              description={copy.noUsersHint}
              action={
                <Button size="sm" onClick={openInvite} disabled={atSeatLimit}>
                  <UserPlus className="size-3.5" aria-hidden />
                  {copy.invite}
                </Button>
              }
            />
          }
        />
      )}

      <DetailDrawer
        open={inviteOpen}
        onClose={closeInvite}
        title={copy.invite}
        description={copy.inviteHint}
        width="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={closeInvite}
              disabled={inviteBusy}
            >
              Cancel
            </Button>
            <Button form={INVITE_FORM_ID} type="submit" disabled={inviteBusy}>
              {inviteBusy ? copy.inviting : copy.inviteAction}
            </Button>
          </div>
        }
      >
        <form id={INVITE_FORM_ID} onSubmit={onInvite} className="grid gap-3">
          <Field label="Name">
            <Input
              value={invite.name}
              onChange={(e) => setInvite({ ...invite, name: e.target.value })}
              required
              autoComplete="name"
            />
          </Field>
          <Field label="Email">
            <Input
              type="email"
              value={invite.email}
              onChange={(e) => setInvite({ ...invite, email: e.target.value })}
              required
              autoComplete="email"
            />
          </Field>
          <Field label="Temporary password" hint="Minimum 8 characters">
            <Input
              type="password"
              value={invite.password}
              onChange={(e) =>
                setInvite({ ...invite, password: e.target.value })
              }
              required
              minLength={8}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Role">
            <Select
              value={invite.role}
              onChange={(e) => setInvite({ ...invite, role: e.target.value })}
            >
              <option value="admin">admin</option>
              <option value="dispatcher">dispatcher</option>
              <option value="technician">technician</option>
            </Select>
          </Field>
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={!!confirmTarget}
        title={
          confirmingDeactivate ? copy.deactivateTitle : copy.reactivateTitle
        }
        description={
          confirmingDeactivate
            ? copy.deactivateBody.replace(
                "{name}",
                confirmTarget?.name || "this teammate",
              )
            : copy.reactivateBody.replace(
                "{name}",
                confirmTarget?.name || "this teammate",
              )
        }
        confirmLabel={
          confirmingDeactivate ? copy.deactivate : copy.reactivate
        }
        danger={confirmingDeactivate}
        busy={rowBusy === confirmTarget?.id}
        onConfirm={() => {
          void onConfirmToggleActive();
        }}
        onCancel={() => {
          if (rowBusy) return;
          setConfirmTarget(null);
        }}
      />
    </AppShell>
  );
}

"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  Button,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
} from "@/components/ui";
import { updateProfile } from "@/lib/api";
import { errors, profile as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import { useAuth } from "@/lib/use-auth";

export default function ProfilePage() {
  const { user, loading, refresh } = useAuth();
  const toast = useToast();
  const [name, setName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user) return;
    queueMicrotask(() => setName(user.name));
  }, [user]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!user) return;
    setError(null);

    if (newPassword || confirmPassword) {
      if (newPassword !== confirmPassword) {
        setError(copy.passwordMismatch);
        return;
      }
      if (!currentPassword) {
        setError("Enter your current password to set a new one.");
        return;
      }
    }

    const body: {
      name?: string;
      current_password?: string;
      new_password?: string;
    } = {};
    if (name.trim() && name.trim() !== user.name) {
      body.name = name.trim();
    }
    if (newPassword) {
      body.current_password = currentPassword;
      body.new_password = newPassword;
    }
    if (!body.name && !body.new_password) {
      setError("Change your name or password before saving.");
      return;
    }

    setBusy(true);
    try {
      const { user: updated } = await updateProfile(body);
      setName(updated.name);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      await refresh();
      toast.push(copy.saved, "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader title={copy.title} description={copy.description} />

      <form onSubmit={onSubmit} className="mx-auto max-w-lg space-y-4">
        <Surface className="space-y-4 p-5">
          <Field label={copy.name}>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoComplete="name"
              maxLength={255}
            />
          </Field>
          <Field label={copy.email} hint={copy.emailReadonly}>
            <Input value={user.email} disabled readOnly />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={copy.role}>
              <Input value={user.role} disabled readOnly className="capitalize" />
            </Field>
            <Field label={copy.business}>
              <Input value={user.tenant_name} disabled readOnly />
            </Field>
          </div>
        </Surface>

        <Surface className="space-y-4 p-5">
          <p className="m-0 text-sm font-medium text-text-primary">Password</p>
          <p className="m-0 text-xs text-text-muted">{copy.passwordHint}</p>
          <Field label={copy.currentPassword}>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
            />
          </Field>
          <Field label={copy.newPassword}>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
            />
          </Field>
          <Field label={copy.confirmPassword}>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
            />
          </Field>
        </Surface>

        {error ? (
          <ErrorState title={errors.saveFailed} message={error} />
        ) : null}

        <Button type="submit" disabled={busy} size="lg">
          {busy ? copy.saving : copy.save}
        </Button>
      </form>
    </AppShell>
  );
}

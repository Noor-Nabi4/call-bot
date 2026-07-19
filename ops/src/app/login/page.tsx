"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { Button, Field, Input, ErrorState } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { user } = await login({
        email,
        password,
        tenant_slug: tenantSlug,
      });
      if (user.role === "technician") router.replace("/tech");
      else router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="ops-shell-atmosphere fixed inset-0 -z-10" aria-hidden />
      <form
        onSubmit={onSubmit}
        className="glass-panel relative z-[1] w-full max-w-md p-6"
      >
        <p className="text-[11px] font-medium tracking-[0.16em] text-text-muted uppercase">
          Call Bot Ops
        </p>
        <h1 className="mt-1 font-heading text-2xl font-semibold tracking-tight">
          Sign in
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Tenant-scoped dispatcher and technician access.
        </p>

        <div className="mt-5 grid gap-3">
          <Field label="Tenant slug">
            <Input
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              required
              autoComplete="organization"
              placeholder="acme-hvac"
            />
          </Field>
          <Field label="Email">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </Field>
        </div>

        {error ? (
          <ErrorState className="mt-4" title="Sign-in failed" message={error} />
        ) : null}

        <Button type="submit" disabled={busy} className="mt-5 w-full" size="lg">
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}

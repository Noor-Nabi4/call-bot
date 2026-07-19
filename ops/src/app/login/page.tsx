"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { Button, Field, Input, ErrorState } from "@/components/ui";
import { login as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";

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
      setError(safeUserError(err, copy.failedMessage));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-12">
      <div className="ops-login-stage fixed inset-0 -z-10" aria-hidden />
      <form
        onSubmit={onSubmit}
        className="relative z-[1] w-full max-w-md rounded-xl border border-white/15 bg-white/95 p-6 shadow-[var(--shadow-elevated)] backdrop-blur-sm sm:p-8"
      >
        <p className="font-heading text-2xl font-semibold tracking-[-0.03em] text-ink">
          {copy.brand}
        </p>
        <h1 className="mt-3 font-heading text-2xl font-semibold tracking-tight text-ink">
          {copy.heading}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">{copy.supporting}</p>

        <div className="mt-6 grid gap-3">
          <Field label={copy.businessId}>
            <Input
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              required
              autoComplete="organization"
              placeholder="your-business"
            />
          </Field>
          <Field label={copy.email}>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </Field>
          <Field label={copy.password}>
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
          <ErrorState
            className="mt-4"
            title={copy.failedTitle}
            message={error}
          />
        ) : null}

        <Button type="submit" disabled={busy} className="mt-6 w-full" size="lg">
          {busy ? copy.submitting : copy.submit}
        </Button>
      </form>
    </div>
  );
}

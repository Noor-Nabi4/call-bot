"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";

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
      else router.replace("/board");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded border border-line bg-panel p-6 shadow-sm"
      >
        <p className="text-xs uppercase tracking-[0.16em] text-ink-muted">
          Call Bot Ops
        </p>
        <h1 className="mt-1 text-2xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Tenant-scoped dispatcher and technician access.
        </p>

        <label className="mt-5 block text-sm font-medium">
          Tenant slug
          <input
            className="mt-1 w-full rounded border border-line px-3 py-2"
            value={tenantSlug}
            onChange={(e) => setTenantSlug(e.target.value)}
            required
            autoComplete="organization"
          />
        </label>
        <label className="mt-3 block text-sm font-medium">
          Email
          <input
            type="email"
            className="mt-1 w-full rounded border border-line px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="username"
          />
        </label>
        <label className="mt-3 block text-sm font-medium">
          Password
          <input
            type="password"
            className="mt-1 w-full rounded border border-line px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>

        {error && (
          <p className="mt-3 text-sm text-danger" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded bg-accent px-3 py-2 font-medium text-white disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

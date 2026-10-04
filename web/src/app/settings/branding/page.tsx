"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Palette } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, branding as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
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

type Branding = {
  product_name?: string | null;
  logo_url?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
  support_email?: string | null;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(errors.saveFailed);
  return res.json();
}

export default function BrandingPage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [form, setForm] = useState<Branding>({
    product_name: "",
    logo_url: "",
    primary_color: "#0F766E",
    accent_color: "",
    support_email: "",
  });
  const [fetching, setFetching] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const data = await api<{ branding: Branding }>("/api/admin/branding");
    setForm({
      product_name: data.branding.product_name || "",
      logo_url: data.branding.logo_url || "",
      primary_color: data.branding.primary_color || "#0F766E",
      accent_color: data.branding.accent_color || "",
      support_email: data.branding.support_email || "",
    });
  }, []);

  useEffect(() => {
    if (!user) return;
    load()
      .catch((e) => toast.push(safeUserError(e, errors.loadFailed), "error"))
      .finally(() => setFetching(false));
  }, [user, load, toast]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/api/admin/branding", {
        method: "PUT",
        body: JSON.stringify({
          product_name: form.product_name || null,
          logo_url: form.logo_url || null,
          primary_color: form.primary_color || null,
          accent_color: form.accent_color || null,
          support_email: form.support_email || null,
        }),
      });
      toast.push(copy.saved, "success");
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
      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <Surface className="max-w-xl p-4">
          <form onSubmit={onSave} className="grid gap-3">
            <Field label={copy.productName}>
              <Input
                value={form.product_name || ""}
                onChange={(e) =>
                  setForm({ ...form, product_name: e.target.value })
                }
                placeholder="Call & Flow"
              />
            </Field>
            <Field label={copy.logoUrl}>
              <Input
                value={form.logo_url || ""}
                onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
                placeholder="https://…"
              />
            </Field>
            <Field label={copy.primaryColor}>
              <Input
                value={form.primary_color || ""}
                onChange={(e) =>
                  setForm({ ...form, primary_color: e.target.value })
                }
                placeholder="#0F766E"
              />
            </Field>
            <Field label={copy.accentColor}>
              <Input
                value={form.accent_color || ""}
                onChange={(e) =>
                  setForm({ ...form, accent_color: e.target.value })
                }
                placeholder="#0ea5e9"
              />
            </Field>
            <Field label={copy.supportEmail}>
              <Input
                type="email"
                value={form.support_email || ""}
                onChange={(e) =>
                  setForm({ ...form, support_email: e.target.value })
                }
              />
            </Field>
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={busy}>
                {busy ? copy.saving : copy.save}
              </Button>
              <span className="inline-flex items-center gap-1 text-xs text-text-muted">
                <Palette className="size-3.5" aria-hidden />
                {copy.hint}
              </span>
            </div>
          </form>
        </Surface>
      )}
    </AppShell>
  );
}

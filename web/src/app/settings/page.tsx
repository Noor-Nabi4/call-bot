"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, Mic, ScrollText, Shield, Users } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, settings as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
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
  PhoneE164Input,
  Select,
  Surface,
  useToast,
  type DataTableColumn,
} from "@/components/ui";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type AuditEvent = {
  id: string;
  created_at?: string | null;
  actor?: string | null;
  action?: string | null;
};

type OrganizationForm = {
  name: string;
  industry: string;
  business_type: string;
  timezone: string;
  currency: string;
  country: string;
  state: string;
  website: string;
  phone: string;
  email: string;
};

const EMPTY_ORG: OrganizationForm = {
  name: "",
  industry: "",
  business_type: "",
  timezone: "UTC",
  currency: "USD",
  country: "",
  state: "",
  website: "",
  phone: "",
  email: "",
};

const BUSINESS_TYPES = [
  ["", "Select…"],
  ["services", "Services"],
  ["products", "Products"],
  ["products_and_services", "Products + services"],
  ["appointments", "Appointments"],
  ["subscriptions", "Subscriptions"],
  ["rentals", "Rentals"],
  ["custom", "Custom"],
] as const;

const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD", "INR", "PKR", "AED", "MXN"];

export default function SettingsPage() {
  const { user, loading, forbidden } = useAuth({ permission: "organization.read" });
  const toast = useToast();
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [retention, setRetention] = useState({
    recording_retention_days: 30,
    transcript_retention_days: 90,
    audit_retention_days: 365,
  });
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [org, setOrg] = useState<OrganizationForm>(EMPTY_ORG);
  const [orgBusy, setOrgBusy] = useState(false);
  const [retentionBusy, setRetentionBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [a, r, o] = await Promise.all([
      fetch(`${API}/api/admin/audit`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
      fetch(`${API}/api/admin/retention`, { credentials: "include" }).then((x) =>
        x.json(),
      ),
      fetch(`${API}/api/admin/organization`, { credentials: "include" }).then(
        (x) => x.json(),
      ),
    ]);
    setAudit(a.events || []);
    if (r.settings) setRetention(r.settings);
    const organization = o.organization;
    if (organization) {
      setOrg({
        name: organization.name || "",
        industry: organization.industry || "",
        business_type: organization.business_type || "",
        timezone: organization.timezone || "UTC",
        currency: organization.currency || "USD",
        country: organization.country || "",
        state: organization.state || "",
        website: organization.website || "",
        phone: organization.phone || "",
        email: organization.email || "",
      });
    }
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

  const auditColumns: DataTableColumn<AuditEvent>[] = [
    {
      id: "time",
      header: "Time",
      cell: (e) => (
        <span className="font-mono text-xs">{String(e.created_at || "—")}</span>
      ),
      mono: true,
    },
    {
      id: "actor",
      header: "Actor",
      cell: (e) => <span>{String(e.actor || "—")}</span>,
    },
    {
      id: "action",
      header: "Action",
      cell: (e) => (
        <span className="font-mono text-xs">{String(e.action || "—")}</span>
      ),
      mono: true,
    },
  ];

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (forbidden) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  async function onSaveOrganization(e: FormEvent) {
    e.preventDefault();
    setOrgBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/organization`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: org.name,
          industry: org.industry || null,
          business_type: org.business_type || null,
          timezone: org.timezone,
          currency: org.currency,
          country: org.country || null,
          state: org.state || null,
          website: org.website || null,
          phone: org.phone || null,
          email: org.email || null,
        }),
      });
      if (!res.ok) throw new Error(errors.saveFailed);
      toast.push(copy.organizationSaved, "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setOrgBusy(false);
    }
  }

  async function onRetention(e: FormEvent) {
    e.preventDefault();
    setRetentionBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/retention`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(retention),
      });
      if (!res.ok) throw new Error(errors.saveFailed);
      toast.push("Retention saved", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setRetentionBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader title={copy.title} description={copy.description} />

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
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="space-y-6">
          <p className="text-sm text-text-secondary">{copy.privacyData}</p>
          <section>
            <div className="mb-3 flex items-center gap-2">
              <Building2 className="size-4 text-text-muted" aria-hidden />
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.organization}
              </h2>
            </div>
            <Surface className="max-w-2xl p-4">
              <p className="mb-3 text-sm text-text-secondary">
                {copy.organizationHint}
              </p>
              <form
                onSubmit={onSaveOrganization}
                className="grid gap-3 sm:grid-cols-2"
              >
                <Field label={copy.name} className="sm:col-span-2">
                  <Input
                    value={org.name}
                    onChange={(e) => setOrg({ ...org, name: e.target.value })}
                    required
                    autoComplete="organization"
                  />
                </Field>
                <Field label={copy.industry}>
                  <Input
                    value={org.industry}
                    onChange={(e) =>
                      setOrg({ ...org, industry: e.target.value })
                    }
                    placeholder="hvac"
                  />
                </Field>
                <Field label={copy.businessType}>
                  <Select
                    value={org.business_type}
                    onChange={(e) =>
                      setOrg({ ...org, business_type: e.target.value })
                    }
                  >
                    {BUSINESS_TYPES.map(([value, label]) => (
                      <option key={value || "none"} value={value}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={copy.timezone}>
                  <Input
                    value={org.timezone}
                    onChange={(e) =>
                      setOrg({ ...org, timezone: e.target.value })
                    }
                    placeholder="America/Chicago"
                  />
                </Field>
                <Field label={copy.currency}>
                  <Select
                    value={org.currency}
                    onChange={(e) =>
                      setOrg({ ...org, currency: e.target.value })
                    }
                  >
                    {Array.from(new Set([org.currency, ...CURRENCIES]))
                      .filter(Boolean)
                      .map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={copy.country}>
                  <Input
                    value={org.country}
                    onChange={(e) =>
                      setOrg({ ...org, country: e.target.value.toUpperCase() })
                    }
                    placeholder="US"
                    maxLength={2}
                  />
                </Field>
                <Field label={copy.state}>
                  <Input
                    value={org.state}
                    onChange={(e) => setOrg({ ...org, state: e.target.value })}
                  />
                </Field>
                <Field label={copy.website} className="sm:col-span-2">
                  <Input
                    type="url"
                    value={org.website}
                    onChange={(e) =>
                      setOrg({ ...org, website: e.target.value })
                    }
                    placeholder="https://"
                  />
                </Field>
                <Field label={copy.phone} className="sm:col-span-2">
                  <PhoneE164Input
                    value={org.phone}
                    countryIso={org.country}
                    onChange={(e164) => setOrg({ ...org, phone: e164 })}
                  />
                </Field>
                <Field label={copy.email} className="sm:col-span-2">
                  <Input
                    type="email"
                    value={org.email}
                    onChange={(e) => setOrg({ ...org, email: e.target.value })}
                    autoComplete="email"
                  />
                </Field>
                <div className="sm:col-span-2">
                  <Button type="submit" disabled={orgBusy} className="w-fit">
                    {orgBusy ? "Saving…" : "Save business profile"}
                  </Button>
                </div>
              </form>
            </Surface>
          </section>
          <Surface className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex items-start gap-2">
              <Mic className="mt-0.5 size-4 text-text-muted" aria-hidden />
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  {copy.assistantLink}
                </h2>
                <p className="text-sm text-text-secondary">
                  {copy.assistantLinkHint}
                </p>
              </div>
            </div>
            <Link
              href="/agents"
              className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
            >
              Open
            </Link>
          </Surface>
          <Surface className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex items-start gap-2">
              <Users className="mt-0.5 size-4 text-text-muted" aria-hidden />
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  {copy.teamLink}
                </h2>
                <p className="text-sm text-text-secondary">{copy.teamLinkHint}</p>
              </div>
            </div>
            <div className="flex gap-2">
              <Link
                href="/settings/roles"
                className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
              >
                Roles
              </Link>
              <Link
                href="/settings/team"
                className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
              >
                Open
              </Link>
            </div>
          </Surface>
          <Surface className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div>
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.billingLink}
              </h2>
              <p className="text-sm text-text-secondary">{copy.billingLinkHint}</p>
            </div>
            <Link
              href="/settings/billing"
              className="rounded-[10px] border border-border bg-surface px-3 py-2 text-sm font-medium hover:bg-surface-2"
            >
              Open
            </Link>
          </Surface>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <Shield className="size-4 text-text-muted" aria-hidden />
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.retention}
              </h2>
            </div>
            <Surface className="max-w-lg p-4">
              <p className="mb-3 text-sm text-text-secondary">
                {copy.privacyRecordings}
              </p>
              <form onSubmit={onRetention} className="grid gap-3">
                {(
                  [
                    ["recording_retention_days", copy.recordings],
                    ["transcript_retention_days", copy.transcripts],
                    ["audit_retention_days", copy.audit],
                  ] as const
                ).map(([key, label]) => (
                  <Field key={key} label={`${label} (days)`}>
                    <Input
                      type="number"
                      value={retention[key]}
                      onChange={(e) =>
                        setRetention({
                          ...retention,
                          [key]: Number(e.target.value),
                        })
                      }
                    />
                  </Field>
                ))}
                <Button type="submit" disabled={retentionBusy} className="w-fit">
                  {retentionBusy ? "Saving…" : "Save retention"}
                </Button>
              </form>
            </Surface>
          </section>

          <section>
            <div className="mb-3 flex items-center gap-2">
              <ScrollText className="size-4 text-text-muted" aria-hidden />
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.audit}
              </h2>
            </div>
            <DataTable
              columns={auditColumns}
              rows={audit}
              className="max-h-96 overflow-y-auto"
              empty={
                <EmptyState
                  title={copy.noAudit}
                  description={copy.noAuditHint}
                />
              }
            />
          </section>
          <p className="text-sm text-text-muted">{copy.privacyConfig}</p>
        </div>
      )}
    </AppShell>
  );
}

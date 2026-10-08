"use client";

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Bot,
  BriefcaseBusiness,
  CalendarCheck,
  CircleDollarSign,
  DollarSign,
  PhoneCall,
  UserPlus,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { formatMoney, formatPercent } from "@/lib/api/metrics";
import type { AdminMetrics } from "@/lib/api/metrics";

export type KpiItem = {
  id: string;
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  href?: string;
};

export function KpiCard({
  item,
  loading,
}: {
  item: KpiItem;
  loading?: boolean;
}) {
  const Icon = item.icon;
  const inner = (
    <div
      className={cn(
        "group flex h-full flex-col gap-3 rounded-[12px] border border-border bg-surface px-4 py-3.5 transition",
        item.href && "hover:border-brand/40 hover:bg-surface-muted/40",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="inline-flex size-9 items-center justify-center rounded-lg border border-border bg-surface-muted/60 text-text-secondary">
          <Icon className="size-5" strokeWidth={1.8} aria-hidden />
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
          {item.label}
        </p>
        {loading ? (
          <div className="mt-2 h-7 w-20 animate-pulse rounded bg-surface-muted" />
        ) : (
          <p className="mt-1 font-heading text-2xl font-semibold tabular-nums tracking-tight text-text-primary">
            {item.value}
          </p>
        )}
        {item.hint ? (
          <p className="mt-1 text-xs text-text-secondary">{item.hint}</p>
        ) : null}
      </div>
    </div>
  );

  if (item.href) {
    return (
      <Link href={item.href} className="block h-full focus-visible:outline-none">
        {inner}
      </Link>
    );
  }
  return inner;
}

export function KpiGrid({
  items,
  loading,
  className,
}: {
  items: KpiItem[];
  loading?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4",
        className,
      )}
      role="list"
      aria-label="Key metrics"
    >
      {items.map((item) => (
        <div key={item.id} role="listitem">
          <KpiCard item={item} loading={loading} />
        </div>
      ))}
    </div>
  );
}

export function buildDashboardKpis(
  metrics: AdminMetrics | null,
  windowDays: number,
): KpiItem[] {
  const period = `Last ${windowDays} days`;
  return [
    {
      id: "calls",
      label: "Calls",
      value: metrics ? metrics.calls.toLocaleString() : "—",
      hint: metrics
        ? `${metrics.calls_ended.toLocaleString()} ended · ${period}`
        : period,
      icon: PhoneCall,
      href: "/calls",
    },
    {
      id: "leads",
      label: "Leads",
      value: metrics ? metrics.leads.toLocaleString() : "—",
      hint: period,
      icon: UserPlus,
      href: "/crm/leads",
    },
    {
      id: "bookings",
      label: "Bookings",
      value: metrics ? metrics.appointments.toLocaleString() : "—",
      hint: metrics
        ? `${metrics.appointment_booked_calls} from AI calls · ${period}`
        : period,
      icon: CalendarCheck,
      href: "/crm/scheduling",
    },
    {
      id: "jobs",
      label: "Jobs",
      value: metrics ? metrics.jobs.toLocaleString() : "—",
      hint: metrics
        ? `${metrics.jobs_completed.toLocaleString()} completed · ${period}`
        : period,
      icon: BriefcaseBusiness,
      href: "/crm/jobs",
    },
    {
      id: "revenue",
      label: "Revenue",
      value: metrics ? formatMoney(metrics.revenue) : "—",
      hint: `Succeeded payments · ${period}`,
      icon: DollarSign,
      href: "/crm/invoices",
    },
    {
      id: "outstanding",
      label: "Outstanding",
      value: metrics ? formatMoney(metrics.outstanding_balance) : "—",
      hint: metrics
        ? `${metrics.outstanding_invoices.toLocaleString()} open invoice${
            metrics.outstanding_invoices === 1 ? "" : "s"
          }`
        : "Open invoice balance",
      icon: CircleDollarSign,
      href: "/crm/invoices",
    },
    {
      id: "ai-resolution",
      label: "AI resolution",
      value: metrics ? formatPercent(metrics.ai_resolution_rate) : "—",
      hint:
        metrics?.ai_resolution_rate == null
          ? "No ended calls in period"
          : `${metrics.handoffs_requested} handoff${
              metrics.handoffs_requested === 1 ? "" : "s"
            } · ${period}`,
      icon: Bot,
      href: "/metrics",
    },
  ];
}

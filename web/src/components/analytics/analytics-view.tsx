"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRightLeft,
  BadgeCheck,
  Bot,
  BriefcaseBusiness,
  CalendarCheck,
  CalendarX,
  Clock3,
  DollarSign,
  Gauge,
  GitBranch,
  Package,
  Phone,
  PhoneCall,
  PhoneMissed,
  Timer,
  UserX,
  Users,
  Wrench,
} from "lucide-react";
import { AppShell } from "@/components/shell";
import { AnalyticsFilters, type AnalyticsFilterState } from "@/components/analytics/filters";
import { AnalyticsKpiGrid, type AnalyticsKpi } from "@/components/analytics/kpi";
import { AnalyticsSeriesChart } from "@/components/analytics/series-chart";
import { DistributionPieChart } from "@/components/ops/raffle-charts";
import { Panel } from "@/components/ops/dashboard";
import {
  formatDurationSeconds,
  getAnalyticsOverview,
  type AnalyticsOverview,
} from "@/lib/api/analytics";
import { formatMoney, formatPercent } from "@/lib/api/metrics";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui";
import { cn } from "@/lib/cn";

type TabId = "overview" | "calls" | "sales" | "operations";

const TABS: { id: TabId; label: string; href: string }[] = [
  { id: "overview", label: "Overview", href: "/analytics" },
  { id: "calls", label: "Calls", href: "/analytics/calls" },
  { id: "sales", label: "Sales", href: "/analytics/sales" },
  { id: "operations", label: "Operations", href: "/analytics/operations" },
];

function seriesFrom(
  rows: { date: string; [k: string]: string | number }[],
  key: string,
): { label: string; value: number }[] {
  return rows.map((r) => ({
    label: String(r.date).slice(5),
    value: Number(r[key] || 0),
  }));
}

export function AnalyticsView({
  initialTab = "overview",
}: {
  initialTab?: TabId;
}) {
  const { user, loading: authLoading, forbidden } = useAuth({
    permission: "analytics.read",
  });
  const [tab, setTab] = useState<TabId>(initialTab);
  const [filters, setFilters] = useState<AnalyticsFilterState>({
    preset: "last_30_days",
    from_date: "",
    to_date: "",
  });
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setFetching(true);
    setError(null);
    try {
      const params =
        filters.preset === "custom"
          ? {
              preset: filters.preset,
              from_date: filters.from_date || undefined,
              to_date: filters.to_date || undefined,
            }
          : { preset: filters.preset };
      const res = await getAnalyticsOverview(params);
      setData(res);
    } catch (err) {
      setError(safeUserError(err));
      setData(null);
    } finally {
      setFetching(false);
    }
  }, [filters]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  const callKpis: AnalyticsKpi[] = useMemo(() => {
    const c = data?.calls;
    return [
      {
        id: "total",
        label: "Total calls",
        value: c ? c.total.toLocaleString() : "—",
        hint: c ? `${c.ended} ended` : undefined,
        icon: Phone,
      },
      {
        id: "answer",
        label: "Answer rate",
        value: formatPercent(c?.answer_rate),
        unavailable: c?.answer_rate_unavailable,
        hint: c?.reviewed_dispositions
          ? `${c.reviewed_dispositions} reviewed`
          : undefined,
        icon: PhoneCall,
      },
      {
        id: "missed",
        label: "Missed calls",
        value: c?.missed != null ? c.missed.toLocaleString() : "—",
        unavailable: c?.missed_unavailable,
        icon: PhoneMissed,
      },
      {
        id: "duration",
        label: "Avg duration",
        value: formatDurationSeconds(c?.average_duration_seconds),
        hint: "Ended calls only",
        icon: Clock3,
      },
      {
        id: "transfer",
        label: "Transfer rate",
        value: formatPercent(c?.transfer_rate),
        hint: c ? `${c.transfers} transfers` : undefined,
        icon: ArrowRightLeft,
      },
      {
        id: "ai",
        label: "AI resolution",
        value: formatPercent(c?.ai_resolution_rate),
        hint: c ? `${c.ai_resolved} resolved without handoff` : undefined,
        icon: Bot,
      },
    ];
  }, [data]);

  const salesKpis: AnalyticsKpi[] = useMemo(() => {
    const s = data?.sales;
    return [
      {
        id: "leads",
        label: "Leads",
        value: s ? s.leads.toLocaleString() : "—",
        icon: Users,
      },
      {
        id: "qualified",
        label: "Qualified leads",
        value: s ? s.qualified_leads.toLocaleString() : "—",
        hint: s?.qualification_rate != null
          ? formatPercent(s.qualification_rate)
          : undefined,
        icon: BadgeCheck,
      },
      {
        id: "bookings",
        label: "Bookings",
        value: s ? s.bookings.toLocaleString() : "—",
        hint: "Excludes cancelled",
        icon: CalendarCheck,
      },
      {
        id: "conversion",
        label: "Conversion",
        value: formatPercent(s?.conversion_rate),
        hint: s ? `${s.converted_leads} booked/won` : undefined,
        icon: GitBranch,
      },
      {
        id: "rpl",
        label: "Revenue / lead",
        value: "—",
        unavailable: s?.revenue_per_lead_unavailable,
        icon: DollarSign,
      },
      {
        id: "rpc",
        label: "Revenue / call",
        value: "—",
        unavailable: s?.revenue_per_call_unavailable,
        icon: Phone,
      },
    ];
  }, [data]);

  const opsKpis: AnalyticsKpi[] = useMemo(() => {
    const o = data?.operations;
    return [
      {
        id: "completed",
        label: "Jobs completed",
        value: o ? o.jobs_completed.toLocaleString() : "—",
        icon: BriefcaseBusiness,
      },
      {
        id: "cancel",
        label: "Cancellation rate",
        value: formatPercent(o?.cancellation_rate),
        hint: o ? `${o.cancelled_jobs} cancelled` : undefined,
        icon: CalendarX,
      },
      {
        id: "noshow",
        label: "No-show rate",
        value: formatPercent(o?.no_show_rate),
        hint: o ? `${o.no_show_count} no-shows` : undefined,
        icon: UserX,
      },
      {
        id: "util",
        label: "Technician utilization",
        value: "—",
        unavailable: o?.technician_utilization_unavailable,
        icon: Gauge,
      },
      {
        id: "jobdur",
        label: "Avg job duration",
        value: formatDurationSeconds(o?.average_job_duration_seconds),
        unavailable: o?.average_job_duration_unavailable,
        icon: Wrench,
      },
      {
        id: "response",
        label: "Avg lead response",
        value: formatDurationSeconds(o?.avg_lead_response_seconds),
        unavailable: o?.avg_lead_response_unavailable,
        icon: Timer,
      },
    ];
  }, [data]);

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
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

  const showCalls = tab === "overview" || tab === "calls";
  const showSales = tab === "overview" || tab === "sales";
  const showOps = tab === "overview" || tab === "operations";

  return (
    <AppShell user={user}>
      <PageHeader
        title="Analytics"
        description="Tenant-scoped call, sales, and operations metrics from live data."
      />

      <nav
        className="mb-4 flex flex-wrap gap-1 border-b border-border"
        aria-label="Analytics sections"
      >
        {TABS.map((t) => (
          <Link
            key={t.id}
            href={t.href}
            onClick={(e) => {
              e.preventDefault();
              setTab(t.id);
              if (typeof window !== "undefined" && window.history) {
                window.history.replaceState(null, "", t.href);
              }
            }}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition",
              tab === t.id
                ? "border-brand text-brand"
                : "border-transparent text-text-secondary hover:text-text-primary",
            )}
            aria-current={tab === t.id ? "page" : undefined}
          >
            {t.label}
          </Link>
        ))}
      </nav>

      <AnalyticsFilters
        className="mb-4"
        value={filters}
        onChange={setFilters}
        timezone={data?.range.timezone}
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => void load()} />
      ) : null}

      {fetching && !data ? (
        <LoadingSkeleton rows={10} />
      ) : !data && !error ? (
        <EmptyState
          title="No analytics data"
          description="There is nothing to show for this range yet."
        />
      ) : data ? (
        <div className="grid gap-6">
          {showCalls ? (
            <section className="grid gap-4" aria-labelledby="calls-heading">
              {tab === "overview" ? (
                <h2
                  id="calls-heading"
                  className="font-heading text-base font-semibold text-text-primary"
                >
                  Calls
                </h2>
              ) : null}
              <AnalyticsKpiGrid items={callKpis} loading={fetching} />
              <div className="grid gap-4 lg:grid-cols-2">
                <AnalyticsSeriesChart
                  title="Calls over time"
                  description="Tenant-local calendar days."
                  data={seriesFrom(data.calls.calls_by_day, "calls")}
                  loading={fetching}
                  emptyMessage="No calls in this period."
                />
                <DistributionPieChart
                  title="Disconnect reasons"
                  description="Among ended calls."
                  data={Object.entries(data.calls.disconnect_reasons).map(
                    ([name, value]) => ({ name, value, status: name }),
                  )}
                  loading={fetching}
                  emptyMessage="No ended-call disconnect data."
                />
              </div>
            </section>
          ) : null}

          {showSales ? (
            <section className="grid gap-4" aria-labelledby="sales-heading">
              {tab === "overview" ? (
                <h2
                  id="sales-heading"
                  className="font-heading text-base font-semibold text-text-primary"
                >
                  Sales
                </h2>
              ) : null}
              <AnalyticsKpiGrid items={salesKpis} loading={fetching} />
              <div className="grid gap-4 lg:grid-cols-2">
                <AnalyticsSeriesChart
                  title="Leads over time"
                  data={seriesFrom(data.sales.leads_by_day, "leads")}
                  loading={fetching}
                  emptyMessage="No leads in this period."
                />
                <AnalyticsSeriesChart
                  title="Bookings over time"
                  data={seriesFrom(data.sales.bookings_by_day, "bookings")}
                  loading={fetching}
                  emptyMessage="No bookings in this period."
                />
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <DistributionPieChart
                  title="Lead funnel"
                  description="Leads → qualified → booked/won (status-based)."
                  data={[
                    {
                      name: "Leads",
                      value: data.sales.funnel.leads,
                      status: "leads",
                    },
                    {
                      name: "Qualified",
                      value: data.sales.funnel.qualified,
                      status: "qualified",
                    },
                    {
                      name: "Booked / won",
                      value: data.sales.funnel.booked_or_won,
                      status: "converted",
                    },
                  ]}
                  loading={fetching}
                  emptyMessage="No lead funnel data."
                />
                <Panel title="Product sales">
                  <p className="mb-3 text-2xl font-semibold tabular-nums text-text-primary">
                    {formatMoney(data.sales.product_sales)}
                  </p>
                  <p className="mb-3 text-xs text-text-muted">
                    Order line totals (excludes draft/cancelled/refunded). Succeeded
                    payments this period: {formatMoney(data.sales.revenue)}.
                  </p>
                  {data.sales.top_products.length === 0 ? (
                    <p className="text-sm text-text-muted">No product sales.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[320px] text-left text-sm">
                        <thead>
                          <tr className="border-b border-border text-xs text-text-muted">
                            <th className="py-2 pr-2 font-medium">Product</th>
                            <th className="py-2 pr-2 font-medium">Units</th>
                            <th className="py-2 font-medium">Revenue</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.sales.top_products.map((p) => (
                            <tr
                              key={`${p.product_id}-${p.name}`}
                              className="border-b border-border/70"
                            >
                              <td className="py-2 pr-2">
                                <span className="inline-flex items-center gap-1.5">
                                  <Package
                                    className="size-3.5 text-text-muted"
                                    aria-hidden
                                  />
                                  {p.name}
                                </span>
                              </td>
                              <td className="py-2 pr-2 tabular-nums">{p.units}</td>
                              <td className="py-2 tabular-nums">
                                {formatMoney(p.revenue)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </Panel>
              </div>
            </section>
          ) : null}

          {showOps ? (
            <section className="grid gap-4" aria-labelledby="ops-heading">
              {tab === "overview" ? (
                <h2
                  id="ops-heading"
                  className="font-heading text-base font-semibold text-text-primary"
                >
                  Operations
                </h2>
              ) : null}
              <AnalyticsKpiGrid items={opsKpis} loading={fetching} />
              <div className="grid gap-4 lg:grid-cols-2">
                <AnalyticsSeriesChart
                  title="Jobs completed over time"
                  data={seriesFrom(
                    data.operations.jobs_completed_by_day,
                    "completed",
                  )}
                  loading={fetching}
                  emptyMessage="No completed jobs in this period."
                />
                <DistributionPieChart
                  title="Jobs by status"
                  description="Jobs created in range."
                  data={Object.entries(data.operations.jobs_by_status).map(
                    ([name, value]) => ({ name, value, status: name }),
                  )}
                  loading={fetching}
                  emptyMessage="No job status data."
                />
              </div>
              <Panel title="Technicians">
                {data.operations.technicians.length === 0 ? (
                  <p className="text-sm text-text-muted">
                    No assigned technicians in this period.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[420px] text-left text-sm">
                      <thead>
                        <tr className="border-b border-border text-xs text-text-muted">
                          <th className="py-2 pr-2 font-medium">Technician</th>
                          <th className="py-2 pr-2 font-medium">Assigned</th>
                          <th className="py-2 pr-2 font-medium">Completed</th>
                          <th className="py-2 font-medium">Utilization</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.operations.technicians.map((t) => (
                          <tr
                            key={t.technician_id}
                            className="border-b border-border/70"
                          >
                            <td className="py-2 pr-2">{t.display_name}</td>
                            <td className="py-2 pr-2 tabular-nums">
                              {t.assigned}
                            </td>
                            <td className="py-2 pr-2 tabular-nums">
                              {t.completed}
                            </td>
                            <td className="py-2 text-text-muted">—</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="mt-2 text-xs text-text-muted">
                      Utilization % is unavailable without clocked available hours.
                    </p>
                  </div>
                )}
              </Panel>
            </section>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}

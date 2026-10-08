"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RefreshCw } from "lucide-react";
import {
  ChartEmptyState,
  ChartSkeleton,
  CHART_COLORS,
  DashboardChartCard,
} from "@/components/ops/charts-shared";
import {
  getCogsCall,
  getCogsScenarios,
  getCogsSummary,
  listCogsCalls,
  type CogsCallRow,
  type CogsPeriod,
  type CogsScenarios,
  type CogsSummary,
} from "@/lib/api/cogs";
import {
  buildCogsBreakdown,
  channelLabel,
  formatCount,
  formatDurationSeconds,
  formatMinutes,
  formatPct,
  formatUsd,
  openaiSourceLabel,
  shortCallId,
  transferLabel,
} from "@/lib/cogs-format";
import { safeUserError } from "@/lib/safe-error";
import { cogs as copy } from "@/lib/ops-copy";
import { UsageCostPanel } from "@/components/ops/usage-cost-panel";
import {
  Button,
  DataTable,
  DetailDrawer,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  MetricSummary,
  PageHeader,
  SearchInput,
  Select,
  Surface,
  type DataTableColumn,
} from "@/components/ui";

const PERIODS: Array<{ value: CogsPeriod; label: string }> = [
  { value: "today", label: "Today" },
  { value: "7d", label: "7 Days" },
  { value: "30d", label: "30 Days" },
  { value: "this_month", label: "This Month" },
  { value: "last_month", label: "Last Month" },
  { value: "custom", label: "Custom" },
];

const PIE_COLORS = [
  CHART_COLORS.primary,
  CHART_COLORS.secondary,
  "#2f6fad",
  "#b45309",
  "#0a6b5d",
  "#5c6d74",
];

function na(value: string): string {
  return value;
}

export function CogsDashboard() {
  const [period, setPeriod] = useState<CogsPeriod>("this_month");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [channel, setChannel] = useState("");
  const [transferKind, setTransferKind] = useState("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 25;

  const [summary, setSummary] = useState<CogsSummary | null>(null);
  const [scenarios, setScenarios] = useState<CogsScenarios | null>(null);
  const [calls, setCalls] = useState<CogsCallRow[]>([]);
  const [callsTotal, setCallsTotal] = useState(0);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CogsCallRow | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(id);
  }, [search]);

  const periodParams = useMemo(() => {
    if (period === "custom") {
      if (!customStart || !customEnd) return null;
      return {
        period: "custom" as const,
        start: new Date(`${customStart}T00:00:00.000Z`).toISOString(),
        end: new Date(`${customEnd}T23:59:59.999Z`).toISOString(),
      };
    }
    return { period };
  }, [period, customStart, customEnd]);

  const refresh = useCallback(async () => {
    if (!periodParams) {
      setError("Choose a custom start and end date.");
      return;
    }
    setError(null);
    const [summaryRes, scenariosRes, callsRes] = await Promise.all([
      getCogsSummary(periodParams),
      getCogsScenarios(),
      listCogsCalls({
        ...periodParams,
        channel: channel || undefined,
        transfer_kind: transferKind || undefined,
        call_id: debouncedSearch || undefined,
        limit,
        offset,
      }),
    ]);
    setSummary(summaryRes.cogs);
    setScenarios(scenariosRes.scenarios);
    setCalls(callsRes.calls);
    setCallsTotal(callsRes.total);
  }, [periodParams, channel, transferKind, debouncedSearch, offset]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setFetching(true);
      refresh()
        .catch((e) => setError(safeUserError(e, copy.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    setOffset(0);
  }, [period, channel, transferKind, debouncedSearch, customStart, customEnd]);

  async function openCall(row: CogsCallRow) {
    setDetailLoading(true);
    setSelected(row);
    try {
      const { call } = await getCogsCall(row.call_id);
      setSelected(call);
    } catch {
      /* keep list row */
    } finally {
      setDetailLoading(false);
    }
  }

  const breakdown = summary
    ? buildCogsBreakdown(summary.variable_cogs)
    : [];

  const kpiItems = summary
    ? [
        {
          label: "Total Revenue",
          value: formatUsd(summary.gross_revenue.total_usd),
          hint: summary.gross_revenue.note,
        },
        {
          label: "Total COGS",
          value: formatUsd(summary.variable_cogs.total_usd),
          hint: "Variable estimated vendor cost",
        },
        {
          label: "Gross Profit",
          value: formatUsd(summary.gross_profit_usd),
        },
        {
          label: "Gross Margin",
          value: formatPct(summary.gross_margin_pct),
        },
        {
          label: "Total Calls",
          value: formatCount(summary.call_count),
        },
        {
          label: "Vendor Minutes",
          value: formatMinutes(summary.vendor_minutes, 2),
          hint: "billable_seconds ÷ 60 (not customer ceil minutes)",
        },
        {
          label: "Avg COGS / Min",
          value: formatUsd(summary.variable_cogs.cogs_per_minute_usd, {
            digits: 4,
          }),
        },
        {
          label: "Avg Revenue / Min",
          value: formatUsd(summary.gross_revenue.revenue_per_minute_usd, {
            digits: 4,
          }),
        },
      ]
    : [];

  const periodBars = summary
    ? [
        {
          name: "Period",
          Revenue: summary.gross_revenue.total_usd ?? 0,
          COGS: summary.variable_cogs.total_usd,
          Profit: summary.gross_profit_usd ?? 0,
        },
      ]
    : [];

  const callColumns: DataTableColumn<CogsCallRow>[] = [
    {
      id: "id",
      header: "Call",
      mono: true,
      cell: (r) => shortCallId(r.call_id),
    },
    {
      id: "date",
      header: "Date",
      cell: (r) =>
        r.started_at
          ? new Date(r.started_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })
          : "—",
    },
    {
      id: "customer",
      header: "Customer",
      cell: (r) => r.customer_name || "—",
    },
    {
      id: "channel",
      header: "Channel",
      cell: (r) => channelLabel(r.channel),
    },
    {
      id: "duration",
      header: "Duration",
      mono: true,
      cell: (r) => formatDurationSeconds(r.billable_seconds),
    },
    {
      id: "billable",
      header: "Billable",
      mono: true,
      cell: (r) => `${r.billable_seconds}s`,
    },
    {
      id: "openai",
      header: "OpenAI",
      mono: true,
      cell: (r) => formatUsd(r.openai_cost_usd, { digits: 4 }),
    },
    {
      id: "livekit",
      header: "LiveKit",
      mono: true,
      cell: (r) =>
        formatUsd(
          r.livekit_agent_cost_usd + r.livekit_sip_cost_usd + r.livekit_bvc_cost_usd,
          { digits: 4 },
        ),
    },
    {
      id: "twilio",
      header: "Twilio",
      mono: true,
      cell: (r) =>
        formatUsd(r.twilio_origination_cost_usd + r.twilio_termination_cost_usd, {
          digits: 4,
        }),
    },
    {
      id: "transfer",
      header: "Transfer",
      cell: (r) => transferLabel(r.transfer_kind),
    },
    {
      id: "total",
      header: "Total COGS",
      mono: true,
      cell: (r) => formatUsd(r.total_estimated_cogs_usd, { digits: 4 }),
    },
    {
      id: "revenue",
      header: "Revenue",
      mono: true,
      cell: () => "N/A",
    },
    {
      id: "profit",
      header: "Profit",
      mono: true,
      cell: () => "N/A",
    },
    {
      id: "margin",
      header: "Margin",
      mono: true,
      cell: () => "N/A",
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setFetching(true);
              refresh()
                .catch((e) => setError(safeUserError(e, copy.loadFailed)))
                .finally(() => setFetching(false));
            }}
          >
            <RefreshCw className="size-3.5" aria-hidden />
            {copy.refresh}
          </Button>
        }
      />

      <UsageCostPanel />

      <FilterBar>
        <div
          className="inline-flex flex-wrap rounded-[10px] border border-border bg-surface-muted p-0.5"
          role="group"
          aria-label="COGS period"
        >
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setPeriod(p.value)}
              className={
                period === p.value
                  ? "rounded-md bg-surface px-2.5 py-1 text-xs font-medium text-text-primary shadow-sm"
                  : "rounded-md px-2.5 py-1 text-xs font-medium text-text-secondary hover:text-text-primary"
              }
            >
              {p.label}
            </button>
          ))}
        </div>
        {period === "custom" ? (
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
              aria-label="Custom start date"
            />
            <span className="text-xs text-text-muted">to</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
              className="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
              aria-label="Custom end date"
            />
          </div>
        ) : null}
        <Select
          value={channel}
          onChange={(e) => setChannel(e.target.value)}
          aria-label="Channel filter"
        >
          <option value="">All channels</option>
          <option value="pstn_sip">PSTN / SIP</option>
          <option value="browser_webrtc">Browser / WebRTC</option>
        </Select>
        <Select
          value={transferKind}
          onChange={(e) => setTransferKind(e.target.value)}
          aria-label="Transfer filter"
        >
          <option value="">All transfers</option>
          <option value="none">No transfer</option>
          <option value="warm">Warm</option>
          <option value="cold">Cold</option>
        </Select>
        <SearchInput
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch("")}
          placeholder={copy.searchPlaceholder}
          aria-label={copy.searchPlaceholder}
        />
      </FilterBar>

      {error ? (
        <ErrorState
          title={copy.errorTitle}
          message={error}
          onRetry={() => {
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, copy.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching && !summary ? (
        <>
          <LoadingSkeleton rows={2} />
          <ChartSkeleton />
          <LoadingSkeleton rows={6} />
        </>
      ) : null}

      {!fetching && summary && summary.call_count === 0 ? (
        <EmptyState title={copy.emptyTitle} description={copy.emptyHint} />
      ) : null}

      {summary ? (
        <>
          <p className="text-xs text-text-muted">
            {copy.estimatedBanner} · {summary.period_start.slice(0, 10)} →{" "}
            {summary.period_end.slice(0, 10)} ({summary.period_kind})
          </p>
          <MetricSummary items={kpiItems} className="lg:grid-cols-4" />

          <div className="grid gap-4 lg:grid-cols-2">
            <DashboardChartCard
              title={copy.periodTotalsTitle}
              description={copy.periodTotalsHint}
            >
              {summary.gross_revenue.total_usd == null ? (
                <ChartEmptyState message={copy.revenueUnavailable} />
              ) : (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={periodBars}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={(value) =>
                          formatUsd(typeof value === "number" ? value : Number(value))
                        }
                      />
                      <Legend />
                      <Bar dataKey="Revenue" fill={CHART_COLORS.primary} />
                      <Bar dataKey="COGS" fill="#b45309" />
                      <Bar dataKey="Profit" fill={CHART_COLORS.secondary} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </DashboardChartCard>

            <DashboardChartCard
              title={copy.dailyCogsTitle}
              description={copy.dailyCogsHint}
            >
              {summary.daily_series.length === 0 ? (
                <ChartEmptyState message={copy.emptyTitle} />
              ) : (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={summary.daily_series}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={(value) =>
                          formatUsd(typeof value === "number" ? value : Number(value), {
                            digits: 4,
                          })
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey="cogs_usd"
                        name="COGS"
                        stroke={CHART_COLORS.primary}
                        strokeWidth={2}
                        dot={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </DashboardChartCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <DashboardChartCard title={copy.breakdownTitle}>
              {breakdown.every((b) => b.usd === 0) ? (
                <ChartEmptyState message={copy.emptyTitle} />
              ) : (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={breakdown.filter((b) => b.usd > 0)}
                        dataKey="usd"
                        nameKey="label"
                        innerRadius={50}
                        outerRadius={80}
                        paddingAngle={2}
                      >
                        {breakdown
                          .filter((b) => b.usd > 0)
                          .map((entry, i) => (
                            <Cell
                              key={entry.key}
                              fill={PIE_COLORS[i % PIE_COLORS.length]}
                            />
                          ))}
                      </Pie>
                      <Tooltip
                        formatter={(value) =>
                          formatUsd(typeof value === "number" ? value : Number(value))
                        }
                      />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </DashboardChartCard>

            <Surface className="p-4">
              <h2 className="mb-3 text-sm font-semibold text-text-primary">
                {copy.breakdownTableTitle}
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-[11px] tracking-wide text-text-muted uppercase">
                    <th className="py-2">Component</th>
                    <th className="py-2 text-right">Cost</th>
                    <th className="py-2 text-right">Share</th>
                  </tr>
                </thead>
                <tbody>
                  {breakdown.map((row) => (
                    <tr key={row.key} className="border-b border-border last:border-0">
                      <td className="py-2 text-text-primary">{row.label}</td>
                      <td className="py-2 text-right font-mono tabular-nums">
                        {formatUsd(row.usd)}
                      </td>
                      <td className="py-2 text-right font-mono tabular-nums">
                        {formatPct(row.pct)}
                      </td>
                    </tr>
                  ))}
                  <tr className="font-semibold">
                    <td className="py-2">Total</td>
                    <td className="py-2 text-right font-mono">
                      {formatUsd(summary.variable_cogs.total_usd)}
                    </td>
                    <td className="py-2 text-right font-mono">100%</td>
                  </tr>
                </tbody>
              </table>
            </Surface>
          </div>

          <Surface className="p-4">
            <h2 className="text-sm font-semibold text-text-primary">
              {copy.fixedTitle}
            </h2>
            <p className="mt-1 text-xs text-text-muted">
              {summary.fixed_monthly.note || copy.fixedHint}
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              <FixedStat
                label="LiveKit fixed"
                value={formatUsd(summary.fixed_monthly.livekit_fixed_monthly_usd)}
              />
              <FixedStat
                label="Phone rental"
                value={formatUsd(summary.fixed_monthly.phone_rental_monthly_usd)}
              />
              <FixedStat
                label="SMS"
                value={formatUsd(summary.fixed_monthly.sms_monthly_usd)}
              />
              <FixedStat
                label="Total fixed"
                value={formatUsd(summary.fixed_monthly.total_fixed_monthly_usd)}
              />
            </div>
          </Surface>

          <Surface className="overflow-hidden p-0">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.planTitle}
              </h2>
              <p className="text-xs text-text-muted">{copy.planHint}</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="bg-surface-muted/70 text-left text-[11px] tracking-wide text-text-muted uppercase">
                  <tr>
                    <th className="px-3 py-2.5">Plan</th>
                    <th className="px-3 py-2.5">Customers</th>
                    <th className="px-3 py-2.5">Minutes</th>
                    <th className="px-3 py-2.5">Revenue</th>
                    <th className="px-3 py-2.5">COGS</th>
                    <th className="px-3 py-2.5">Gross Profit</th>
                    <th className="px-3 py-2.5">Margin</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.plan_profitability.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-3 py-6 text-center text-text-muted">
                        N/A
                      </td>
                    </tr>
                  ) : (
                    summary.plan_profitability.map((row) => (
                      <tr key={row.plan_key} className="border-t border-border">
                        <td className="px-3 py-2.5 capitalize">{row.plan_key}</td>
                        <td className="px-3 py-2.5 font-mono">
                          {row.customers == null ? "N/A" : formatCount(row.customers)}
                        </td>
                        <td className="px-3 py-2.5 font-mono">
                          {formatMinutes(row.vendor_minutes, 2)}
                        </td>
                        <td className="px-3 py-2.5 font-mono">
                          {formatUsd(row.revenue_usd)}
                        </td>
                        <td className="px-3 py-2.5 font-mono">
                          {formatUsd(row.cogs_usd)}
                        </td>
                        <td className="px-3 py-2.5 font-mono">
                          {formatUsd(row.gross_profit_usd)}
                        </td>
                        <td className="px-3 py-2.5 font-mono">
                          {formatPct(row.gross_margin_pct)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Surface>

          <Surface className="overflow-hidden p-0">
            <div className="border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-text-primary">
                {copy.channelTitle}
              </h2>
              <p className="text-xs text-text-muted">{copy.channelHint}</p>
            </div>
            <ChannelTable rows={summary.by_channel} kind="channel" />
            <div className="border-t border-border px-4 py-2 text-xs font-medium text-text-muted">
              Transfers
            </div>
            <ChannelTable rows={summary.by_transfer_kind} kind="transfer" />
          </Surface>

          {scenarios ? <ScenariosPanel scenarios={scenarios} /> : null}

          <Surface className="overflow-hidden p-0">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold text-text-primary">
                  {copy.callsTitle}
                </h2>
                <p className="text-xs text-text-muted">{copy.callsHint}</p>
              </div>
              <p className="text-xs text-text-muted">
                {formatCount(callsTotal)} calls
              </p>
            </div>
            <DataTable
              columns={callColumns}
              rows={calls}
              onRowClick={openCall}
              selectedId={selected?.id}
              empty={
                <EmptyState title={copy.emptyTitle} description={copy.emptyHint} />
              }
            />
            <div className="flex items-center justify-between border-t border-border px-4 py-2">
              <Button
                type="button"
                variant="secondary"
                disabled={offset <= 0}
                onClick={() => setOffset((o) => Math.max(0, o - limit))}
              >
                Previous
              </Button>
              <span className="text-xs text-text-muted">
                {offset + 1}–{Math.min(offset + limit, callsTotal)} of {callsTotal}
              </span>
              <Button
                type="button"
                variant="secondary"
                disabled={offset + limit >= callsTotal}
                onClick={() => setOffset((o) => o + limit)}
              >
                Next
              </Button>
            </div>
          </Surface>
        </>
      ) : null}

      <DetailDrawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? shortCallId(selected.call_id) : "Call COGS"}
        description={detailLoading ? "Loading…" : copy.detailHint}
        width="lg"
      >
        {selected ? <CallDetailBody call={selected} /> : null}
      </DetailDrawer>
    </div>
  );
}

function FixedStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-muted/40 px-3 py-2">
      <p className="text-[11px] tracking-wide text-text-muted uppercase">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function ChannelTable({
  rows,
  kind,
}: {
  rows: CogsSummary["by_channel"];
  kind: "channel" | "transfer";
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead className="bg-surface-muted/40 text-left text-[11px] tracking-wide text-text-muted uppercase">
          <tr>
            <th className="px-3 py-2">{kind === "channel" ? "Channel" : "Transfer"}</th>
            <th className="px-3 py-2">Calls</th>
            <th className="px-3 py-2">Minutes</th>
            <th className="px-3 py-2">COGS</th>
            <th className="px-3 py-2">COGS/min</th>
            <th className="px-3 py-2">Revenue</th>
            <th className="px-3 py-2">Profit</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-3 py-4 text-center text-text-muted">
                N/A
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.key} className="border-t border-border">
                <td className="px-3 py-2">
                  {kind === "channel"
                    ? channelLabel(row.key)
                    : transferLabel(row.key)}
                </td>
                <td className="px-3 py-2 font-mono">{formatCount(row.call_count)}</td>
                <td className="px-3 py-2 font-mono">
                  {formatMinutes(row.vendor_minutes, 2)}
                </td>
                <td className="px-3 py-2 font-mono">
                  {formatUsd(row.total_estimated_cogs_usd)}
                </td>
                <td className="px-3 py-2 font-mono">
                  {formatUsd(row.cogs_per_minute_usd ?? null, { digits: 4 })}
                </td>
                <td className="px-3 py-2 font-mono">
                  {na(formatUsd(row.revenue_usd ?? null))}
                </td>
                <td className="px-3 py-2 font-mono">
                  {na(formatUsd(row.gross_profit_usd ?? null))}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function ScenariosPanel({ scenarios }: { scenarios: CogsScenarios }) {
  const ship = scenarios.ship_vs_scale.ship;
  const scale = scenarios.ship_vs_scale.scale;
  return (
    <Surface className="p-4">
      <h2 className="text-sm font-semibold text-text-primary">Cost Scenarios</h2>
      <p className="mt-1 text-xs text-text-muted">
        Estimated variable vendor COGS — not actual invoices.
      </p>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[480px] text-sm">
          <thead className="text-left text-[11px] tracking-wide text-text-muted uppercase">
            <tr>
              <th className="py-2">Minutes</th>
              <th className="py-2">Ship</th>
              <th className="py-2">Scale</th>
            </tr>
          </thead>
          <tbody>
            {ship.map((row, i) => (
              <tr key={row.minutes} className="border-t border-border">
                <td className="py-2 font-mono">{formatCount(row.minutes)}</td>
                <td className="py-2 font-mono">
                  {formatUsd(row.variable.total_variable_usd)}
                </td>
                <td className="py-2 font-mono">
                  {formatUsd(scale[i]?.variable.total_variable_usd ?? null)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {(["low", "base", "high"] as const).map((key) => {
          const rows = scenarios.openai_sensitivity.scenarios[key] || [];
          const first = rows[0];
          return (
            <div
              key={key}
              className="rounded-md border border-border bg-surface-muted/40 px-3 py-2"
            >
              <p className="text-[11px] tracking-wide text-text-muted uppercase">
                OpenAI {key}
              </p>
              <p className="mt-0.5 font-mono text-sm font-semibold">
                {formatUsd(first?.openai_per_minute_usd ?? null, { digits: 4 })}
                /min
              </p>
              <p className="text-xs text-text-secondary">
                1k min → {formatUsd(first?.variable.total_variable_usd ?? null)}
              </p>
            </div>
          );
        })}
      </div>
      <div className="mt-4 rounded-md border border-dashed border-border px-3 py-2 text-xs text-text-secondary">
        <p className="font-medium text-text-primary">Fixed platform costs (configured)</p>
        <p className="mt-1 font-mono">
          LiveKit {formatUsd(scenarios.fixed_monthly.livekit_fixed_monthly_usd)} · Phone{" "}
          {formatUsd(scenarios.fixed_monthly.phone_rental_monthly_usd)} · SMS{" "}
          {formatUsd(scenarios.fixed_monthly.sms_monthly_usd)}
        </p>
      </div>
    </Surface>
  );
}

function CallDetailBody({ call }: { call: CogsCallRow }) {
  const usage = call.openai_usage || {};
  return (
    <div className="space-y-5 text-sm">
      <section>
        <h3 className="text-xs font-semibold tracking-wide text-text-muted uppercase">
          Call information
        </h3>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <DetailItem label="Call ID" value={call.call_id} mono />
          <DetailItem label="Customer" value={call.customer_name || "—"} />
          <DetailItem label="Started" value={call.started_at || "—"} />
          <DetailItem label="Ended" value={call.ended_at || "—"} />
          <DetailItem label="Channel" value={channelLabel(call.channel)} />
          <DetailItem label="Transfer" value={transferLabel(call.transfer_kind)} />
          <DetailItem
            label="Duration"
            value={formatDurationSeconds(call.billable_seconds)}
          />
          <DetailItem
            label="Billable seconds"
            value={String(call.billable_seconds)}
            mono
          />
        </dl>
      </section>

      <section>
        <h3 className="text-xs font-semibold tracking-wide text-text-muted uppercase">
          OpenAI usage
        </h3>
        <p className="mt-1 text-xs text-text-secondary">
          Usage source: {openaiSourceLabel(call.openai_cost_source)}
        </p>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <DetailItem
            label="Audio input tokens"
            value={String(usage.input_audio_tokens ?? "N/A")}
            mono
          />
          <DetailItem
            label="Cached audio input"
            value={String(usage.input_cached_audio_tokens ?? "N/A")}
            mono
          />
          <DetailItem
            label="Audio output tokens"
            value={String(usage.output_audio_tokens ?? "N/A")}
            mono
          />
          <DetailItem
            label="Text input tokens"
            value={String(usage.input_text_tokens ?? "N/A")}
            mono
          />
          <DetailItem
            label="Cached text input"
            value={String(usage.input_cached_text_tokens ?? "N/A")}
            mono
          />
          <DetailItem
            label="Text output tokens"
            value={String(usage.output_text_tokens ?? "N/A")}
            mono
          />
        </dl>
      </section>

      <section>
        <h3 className="text-xs font-semibold tracking-wide text-text-muted uppercase">
          Estimated COGS
        </h3>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <DetailItem label="OpenAI" value={formatUsd(call.openai_cost_usd, { digits: 4 })} mono />
          <DetailItem
            label="LiveKit Agent"
            value={formatUsd(call.livekit_agent_cost_usd, { digits: 4 })}
            mono
          />
          <DetailItem
            label="LiveKit SIP"
            value={formatUsd(call.livekit_sip_cost_usd, { digits: 4 })}
            mono
          />
          <DetailItem
            label="BVC"
            value={formatUsd(call.livekit_bvc_cost_usd, { digits: 4 })}
            mono
          />
          <DetailItem
            label="Twilio origination"
            value={formatUsd(call.twilio_origination_cost_usd, { digits: 4 })}
            mono
          />
          <DetailItem
            label="Twilio termination"
            value={formatUsd(call.twilio_termination_cost_usd, { digits: 4 })}
            mono
          />
          <DetailItem
            label="Total"
            value={formatUsd(call.total_estimated_cogs_usd, { digits: 4 })}
            mono
          />
        </dl>
      </section>

      <section>
        <h3 className="text-xs font-semibold tracking-wide text-text-muted uppercase">
          Revenue
        </h3>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <DetailItem label="Revenue" value="N/A" />
          <DetailItem label="Gross profit" value="N/A" />
          <DetailItem label="Gross margin" value="N/A" />
        </dl>
        <p className="mt-2 text-xs text-text-muted">
          Subscription revenue is not allocated per call.
        </p>
      </section>
    </div>
  );
}

function DetailItem({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-[11px] text-text-muted">{label}</dt>
      <dd className={mono ? "font-mono text-text-primary break-all" : "text-text-primary"}>
        {value}
      </dd>
    </div>
  );
}

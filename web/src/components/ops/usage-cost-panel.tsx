"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartEmptyState,
  ChartSkeleton,
  CHART_COLORS,
  DashboardChartCard,
} from "@/components/ops/charts-shared";
import {
  getUsageCostSummary,
  type LimitStatus,
  type UsageCostSummary,
} from "@/lib/api/usage-cost";
import {
  formatNullablePct,
  formatNullableUsd,
  provenanceLabel,
} from "@/lib/api/usage-cost-format";
import { safeUserError } from "@/lib/safe-error";
import { ErrorState, MetricSummary, Surface } from "@/components/ui";

function fmtTokens(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

function fmtBytes(n: number): string {
  if (n <= 0) return "0 B";
  const gb = n / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(2)} GiB`;
  const mb = n / 1024 ** 2;
  if (mb >= 1) return `${mb.toFixed(1)} MiB`;
  return `${n} B`;
}

function Badge({ children }: { children: string }) {
  return (
    <span className="ml-1 rounded border border-border px-1 py-0.5 text-[10px] font-medium tracking-wide text-text-muted uppercase">
      {children}
    </span>
  );
}

export function UsageCostPanel() {
  const [data, setData] = useState<UsageCostSummary | null>(null);
  const [limits, setLimits] = useState<LimitStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getUsageCostSummary()
      .then((res) => {
        if (cancelled) return;
        setData(res.usage_cost);
        setLimits(res.limit_status);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(safeUserError(e, "Could not load usage costs."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <ChartSkeleton className="h-48" />;
  }
  if (error) {
    return <ErrorState message={error} />;
  }
  if (!data) {
    return <ChartEmptyState message="No usage ledger data for this period." />;
  }

  const u = data.usage;
  const cost = data.cost;
  const rev = data.revenue;
  const margin = data.gross_margin;
  const costProv = cost.provenance || {};
  const trend = data.daily_series.map((d) => ({
    date: d.date.slice(5),
    cost: d.cost_usd ?? 0,
    voice: d.usage.VOICE_MINUTES ?? 0,
    requests: d.usage.AI_REQUESTS ?? 0,
  }));

  return (
    <div className="space-y-4">
      <Surface className="space-y-3 p-4">
        <div>
          <h2 className="text-base font-semibold">Usage ledger (this month)</h2>
          <p className="text-sm text-text-muted">
            Values show provenance badges. Estimated overage is never labeled as
            actual Stripe revenue. Missing infrastructure is N/A, not $0.
          </p>
        </div>

        <MetricSummary
          items={[
            {
              label: "Voice minutes",
              value: String(u.voice_minutes),
              hint: provenanceLabel(u.provenance?.voice_minutes),
            },
            {
              label: "LLM in / out",
              value: `${fmtTokens(u.llm_input_tokens)} / ${fmtTokens(u.llm_output_tokens)}`,
              hint: provenanceLabel(u.provenance?.llm_tokens),
            },
            { label: "AI requests", value: String(u.ai_requests) },
            { label: "Tool calls", value: String(u.tool_calls) },
            {
              label: "SMS",
              value: String(u.sms),
              hint: provenanceLabel(u.provenance?.sms),
            },
            {
              label: "Transcription",
              value: `${u.transcription_seconds}s`,
              hint: provenanceLabel(u.provenance?.transcription),
            },
            {
              label: "Storage",
              value: fmtBytes(u.storage_bytes),
              hint: provenanceLabel(u.provenance?.storage),
            },
          ]}
        />

        <div className="space-y-2">
          <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
            Revenue
          </p>
          <MetricSummary
            items={[
              {
                label: "Actual revenue",
                value: formatNullableUsd(rev.actual_revenue_usd ?? null),
                hint: provenanceLabel(rev.actual_revenue_provenance),
              },
              {
                label: "Configured subscription",
                value: formatNullableUsd(
                  rev.configured_subscription_revenue_usd ??
                    (rev.subscription_cents != null
                      ? rev.subscription_cents / 100
                      : null),
                ),
                hint: provenanceLabel(rev.configured_subscription_provenance),
              },
              {
                label: "Estimated overage",
                value: formatNullableUsd(
                  rev.estimated_overage_revenue_usd ??
                    (rev.estimated_overage_cents != null
                      ? rev.estimated_overage_cents / 100
                      : null),
                ),
                hint: `${provenanceLabel(rev.estimated_overage_provenance)} · not invoiced`,
              },
            ]}
          />
          <p className="text-xs text-text-muted">{rev.note}</p>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
            COGS
          </p>
          <MetricSummary
            items={[
              {
                label: "Voice COGS",
                value: formatNullableUsd(cost.voice_usd),
                hint: provenanceLabel(costProv.voice),
              },
              {
                label: "LLM COGS",
                value: formatNullableUsd(cost.llm_usd),
                hint: provenanceLabel(costProv.llm),
              },
              {
                label: "SMS COGS",
                value: formatNullableUsd(cost.sms_usd),
                hint: provenanceLabel(costProv.sms),
              },
              {
                label: "Infrastructure",
                value: formatNullableUsd(cost.infrastructure_usd),
                hint: provenanceLabel(costProv.infrastructure),
              },
              {
                label: "Calculated COGS",
                value: formatNullableUsd(cost.total_cogs_usd),
                hint: "Configured + allocated (not vendor invoice)",
              },
            ]}
          />
        </div>

        <div className="space-y-2">
          <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
            Gross margin
          </p>
          <MetricSummary
            items={[
              {
                label: "Actual gross margin",
                value: formatNullableUsd(margin.actual_gross_margin_usd ?? null),
                hint: margin.verified
                  ? "Verified"
                  : "Unavailable — needs Stripe invoice amounts",
              },
              {
                label: "Calculated gross margin",
                value: formatNullableUsd(
                  margin.calculated_gross_margin_usd ?? margin.gross_margin_usd,
                ),
                hint: formatNullablePct(
                  margin.calculated_gross_margin_pct ?? margin.gross_margin_pct,
                ),
              },
              {
                label: "Margin confidence",
                value: margin.verified ? "Verified" : "Unverified",
                hint: "Estimated overage excluded from calculated margin",
              },
            ]}
          />
          {margin.note ? (
            <p className="text-xs text-text-muted">{margin.note}</p>
          ) : null}
        </div>

        {limits ? (
          <p className="text-xs text-text-muted">
            Voice limit: {limits.used}
            {limits.limit != null ? ` / ${limits.limit}` : ""} minutes · state{" "}
            {limits.state}
            {limits.percent != null ? ` (${limits.percent}%)` : ""} ·{" "}
            {limits.note}
          </p>
        ) : null}
        {data.stripe_metering ? (
          <p className="text-xs text-text-muted">
            Stripe metering: {data.stripe_metering.status}
            <Badge>{data.stripe_metering.wired ? "Wired" : "Not wired"}</Badge>
            {" — "}
            {data.stripe_metering.note}
          </p>
        ) : null}
      </Surface>

      <DashboardChartCard
        title="Usage & calculated cost trend"
        description="UTC calendar month · configured-rate COGS"
      >
        {trend.length === 0 ? (
          <ChartEmptyState message="No daily usage yet this period." />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="voice"
                name="Voice min"
                stroke={CHART_COLORS.primary}
                fill={CHART_COLORS.primary}
                fillOpacity={0.15}
              />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="requests"
                name="AI requests"
                stroke={CHART_COLORS.secondary}
                fill={CHART_COLORS.secondary}
                fillOpacity={0.12}
              />
              <Area
                yAxisId="right"
                type="monotone"
                dataKey="cost"
                name="Calculated COGS USD"
                stroke="#b45309"
                fill="#b45309"
                fillOpacity={0.1}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </DashboardChartCard>
    </div>
  );
}

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

/**
 * Organization-safe usage panel.
 * Never renders platform COGS, provider costs, or gross margin.
 */
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
        if (!cancelled) setError(safeUserError(e, "Could not load usage."));
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
    return <ChartEmptyState message="No usage data for this period." />;
  }

  const u = data.usage;
  const billing = data.billing;
  const trend = data.daily_series.map((d) => ({
    date: (d.date || "").slice(5),
    voice: d.usage.VOICE_MINUTES ?? 0,
    requests: d.usage.AI_REQUESTS ?? 0,
    sms: d.usage.SMS ?? 0,
  }));

  return (
    <div className="space-y-4">
      <Surface className="space-y-3 p-4">
        <div>
          <h2 className="text-base font-semibold">Usage (this month)</h2>
          <p className="text-sm text-text-muted">
            Your organization&apos;s consumption and plan limits. Estimated
            overage is not a finalized invoice.
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
            Plan &amp; overage
          </p>
          <MetricSummary
            items={[
              {
                label: "Included minutes",
                value:
                  data.limits.included_minutes != null
                    ? String(data.limits.included_minutes)
                    : "—",
              },
              {
                label: "Overage minutes",
                value: String(data.limits.overage_minutes ?? 0),
              },
              {
                label: "Estimated overage",
                value: formatNullableUsd(billing.estimated_overage_usd),
                hint: "Estimated · not invoiced",
              },
            ]}
          />
          <p className="text-xs text-text-muted">{billing.note}</p>
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
      </Surface>

      <DashboardChartCard
        title="Usage trend"
        description="UTC calendar month · organization consumption only"
      >
        {trend.length === 0 ? (
          <ChartEmptyState message="No daily usage yet this period." />
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="voice"
                name="Voice min"
                stroke={CHART_COLORS.primary}
                fill={CHART_COLORS.primary}
                fillOpacity={0.15}
              />
              <Area
                type="monotone"
                dataKey="requests"
                name="AI requests"
                stroke={CHART_COLORS.secondary}
                fill={CHART_COLORS.secondary}
                fillOpacity={0.12}
              />
              <Area
                type="monotone"
                dataKey="sms"
                name="SMS"
                stroke="#0f766e"
                fill="#0f766e"
                fillOpacity={0.1}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </DashboardChartCard>
    </div>
  );
}

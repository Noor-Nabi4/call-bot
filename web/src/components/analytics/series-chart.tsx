"use client";

import {
  Bar,
  BarChart,
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

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid rgba(15,23,42,0.08)",
  background: "#fff",
  fontSize: 12,
  color: "#111827",
};

export function AnalyticsSeriesChart({
  title,
  description,
  data,
  dataKey,
  loading,
  emptyMessage,
}: {
  title: string;
  description?: string;
  data: { label: string; value: number }[];
  dataKey?: string;
  loading?: boolean;
  emptyMessage?: string;
}) {
  const key = dataKey || "value";
  const hasData = data.some((d) => d.value > 0);

  return (
    <DashboardChartCard title={title} description={description}>
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <ChartEmptyState message={emptyMessage || "No data for this period."} />
      ) : (
        <div className="h-52 w-full" role="img" aria-label={title}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={36}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar
                dataKey={key}
                name={title}
                fill={CHART_COLORS.primary}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashboardChartCard>
  );
}

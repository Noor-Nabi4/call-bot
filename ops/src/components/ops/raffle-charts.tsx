"use client";

/**
 * Recharts distribution / bar charts (Raffle Home.jsx patterns).
 * CanvasJS vendor removed — lighter bundle, no commercial chart license.
 */

import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  Legend,
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChartEmptyState,
  ChartSkeleton,
  CHART_COLORS,
  DashboardChartCard,
} from "@/components/ops/charts-shared";

export const RAFFLE_COLORS = [
  "#7c3aed",
  "#22d3ee",
  "#5B9BD5",
  "#70AD47",
  "#ED7D31",
  "#A5A5A5",
  "#FFC000",
  "#4472C4",
  "#34d399",
  "#f59e0b",
  "#f87171",
  "#94a3b8",
] as const;

/** Fixed brand colors for job statuses (not rotating palette). */
export const JOB_STATUS_COLORS: Record<string, string> = {
  new: "#22d3ee",
  scheduled: "#7c3aed",
  dispatched: "#6366f1",
  in_progress: "#f59e0b",
  completed: "#34d399",
  canceled: "#f87171",
  cancelled: "#f87171",
};

/** Fixed brand colors for call statuses. */
export const CALL_STATUS_COLORS: Record<string, string> = {
  ringing: "#22d3ee",
  initiated: "#22d3ee",
  in_progress: "#f59e0b",
  active: "#f59e0b",
  answered: "#7c3aed",
  completed: "#34d399",
  ended: "#34d399",
  success: "#34d399",
  failed: "#f87171",
  busy: "#ed7d31",
  no_answer: "#94a3b8",
  canceled: "#f87171",
  cancelled: "#f87171",
  unknown: "#64748b",
};

export function colorForJobStatus(status: string): string {
  const key = status.toLowerCase();
  return JOB_STATUS_COLORS[key] || RAFFLE_COLORS[0];
}

export function colorForCallStatus(status: string): string {
  const key = status.toLowerCase();
  return CALL_STATUS_COLORS[key] || RAFFLE_COLORS[5];
}

export type DistributionPoint = {
  /** Display label */
  name: string;
  value: number;
  color?: string;
  /** Raw status key for navigation / filters */
  status?: string;
};

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "#0c101c",
  boxShadow: "0 16px 48px rgba(0,0,0,0.45)",
  fontSize: 12,
  color: "#f8fafc",
};

export function DistributionPieChart({
  title,
  description,
  data,
  loading,
  emptyMessage,
  onSliceClick,
}: {
  title: string;
  description?: string;
  data: DistributionPoint[];
  loading?: boolean;
  emptyMessage?: string;
  onSliceClick?: (point: DistributionPoint) => void;
}) {
  const points = data.filter((d) => d.value > 0);
  const hasData = points.length > 0;
  const interactive = typeof onSliceClick === "function";

  return (
    <DashboardChartCard title={title} description={description}>
      {loading ? (
        <ChartSkeleton className="h-56" />
      ) : !hasData ? (
        <ChartEmptyState
          message={
            emptyMessage ?? "No activity data is available for this period."
          }
        />
      ) : (
        <div
          className={interactive ? "h-56 w-full cursor-pointer" : "h-56 w-full"}
          role="img"
          aria-label={
            interactive
              ? `${title}. Click a slice to filter.`
              : title
          }
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={points}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={78}
                innerRadius={36}
                paddingAngle={2}
                isAnimationActive={false}
                style={interactive ? { cursor: "pointer" } : undefined}
                onClick={(_, index) => {
                  if (!interactive) return;
                  const point = points[index];
                  if (point) onSliceClick(point);
                }}
              >
                {points.map((entry, index) => (
                  <Cell
                    key={entry.status || entry.name}
                    fill={
                      entry.color ||
                      RAFFLE_COLORS[index % RAFFLE_COLORS.length]
                    }
                    stroke="transparent"
                    style={interactive ? { cursor: "pointer" } : undefined}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={tooltipStyle}
                formatter={(value, name) => [
                  Number(value ?? 0),
                  String(name ?? ""),
                ]}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
                iconType="circle"
                iconSize={8}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashboardChartCard>
  );
}

/** Raffle CustomBarGraph style — single-series vertical bars. */
export function SingleSeriesBarChart({
  title,
  description,
  data,
  loading,
  valueKey = "value",
  nameKey = "name",
  barColor = CHART_COLORS.primary,
}: {
  title: string;
  description?: string;
  data: Record<string, string | number>[];
  loading?: boolean;
  valueKey?: string;
  nameKey?: string;
  barColor?: string;
}) {
  const hasData = data.some((d) => Number(d[valueKey] || 0) > 0);

  return (
    <DashboardChartCard title={title} description={description}>
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <ChartEmptyState />
      ) : (
        <div className="h-52 w-full" role="img" aria-label={title}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 12, right: 12, left: 0, bottom: 8 }}
            >
              <CartesianGrid
                stroke={CHART_COLORS.grid}
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey={nameKey}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                width={32}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar
                dataKey={valueKey}
                fill={barColor}
                radius={[6, 6, 0, 0]}
                maxBarSize={48}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashboardChartCard>
  );
}

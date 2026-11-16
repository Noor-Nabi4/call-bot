"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Link from "next/link";
import {
  ChartEmptyState,
  ChartSkeleton,
  CHART_COLORS,
  DashboardChartCard,
  DateRangeSelector,
  type DateRangeDays,
} from "@/components/ops/charts-shared";

type JobsPoint = {
  label: string;
  created: number;
  completed: number;
};

type CallsPoint = {
  label: string;
  calls: number;
  ended: number;
  appointments: number;
};

type WorkloadRow = {
  name: string;
  assigned: number;
  active: number;
};

const tooltipStyle = {
  borderRadius: 12,
  border: "1px solid rgba(255,255,255,0.1)",
  background: "#0c101c",
  boxShadow: "0 16px 48px rgba(0,0,0,0.45)",
  fontSize: 12,
  color: "#f8fafc",
};

export function JobsActivityChart({
  data,
  rangeDays,
  onRangeChange,
  loading,
}: {
  data: JobsPoint[];
  rangeDays: DateRangeDays;
  onRangeChange: (days: DateRangeDays) => void;
  loading?: boolean;
}) {
  const hasData = data.some((d) => d.created > 0 || d.completed > 0);

  return (
    <DashboardChartCard
      title="Jobs activity"
      description="Created vs completed jobs in the selected window."
      action={
        <DateRangeSelector value={rangeDays} onChange={onRangeChange} />
      }
    >
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <ChartEmptyState />
      ) : (
        <div className="h-52 w-full" role="img" aria-label="Jobs created and completed">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                width={28}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend
                wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                iconType="circle"
                iconSize={8}
              />
              <Area
                type="monotone"
                dataKey="created"
                name="Created"
                stroke={CHART_COLORS.primary}
                fill={CHART_COLORS.primary}
                fillOpacity={0.12}
                strokeWidth={2}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="completed"
                name="Completed"
                stroke={CHART_COLORS.secondary}
                fill={CHART_COLORS.secondary}
                fillOpacity={0.08}
                strokeWidth={2}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashboardChartCard>
  );
}

export function CallsBookingChart({
  data,
  rangeDays,
  onRangeChange,
  loading,
}: {
  data: CallsPoint[];
  rangeDays: DateRangeDays;
  onRangeChange?: (days: DateRangeDays) => void;
  loading?: boolean;
}) {
  const hasData = data.some(
    (d) => d.calls > 0 || d.ended > 0 || d.appointments > 0,
  );

  return (
    <DashboardChartCard
      title="Calls and bookings"
      description={`Total calls, ended calls, and appointments · last ${rangeDays} days.`}
      action={
        onRangeChange ? (
          <DateRangeSelector value={rangeDays} onChange={onRangeChange} />
        ) : undefined
      }
    >
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <ChartEmptyState />
      ) : (
        <div
          className="h-52 w-full"
          role="img"
          aria-label="Calls and appointments by day"
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                width={28}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend
                wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                iconType="circle"
                iconSize={8}
              />
              <Bar
                dataKey="calls"
                name="Calls"
                fill={CHART_COLORS.primary}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
              <Bar
                dataKey="ended"
                name="Ended"
                fill={CHART_COLORS.secondary}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
              <Bar
                dataKey="appointments"
                name="Appointments"
                fill={CHART_COLORS.tertiary}
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

export function RevenueChart({
  data,
  rangeDays,
  onRangeChange,
  loading,
}: {
  data: { label: string; revenue: number }[];
  rangeDays: DateRangeDays;
  onRangeChange: (days: DateRangeDays) => void;
  loading?: boolean;
}) {
  const hasData = data.some((d) => d.revenue > 0);

  return (
    <DashboardChartCard
      title="Revenue"
      description="Succeeded payments in the selected window."
      action={
        <DateRangeSelector value={rangeDays} onChange={onRangeChange} />
      }
    >
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <ChartEmptyState message="No payment revenue in this period." />
      ) : (
        <div className="h-52 w-full" role="img" aria-label="Revenue over time">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="revFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={CHART_COLORS.primary} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" />
              <XAxis
                dataKey="label"
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={56}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Area
                type="monotone"
                dataKey="revenue"
                name="Revenue"
                stroke={CHART_COLORS.primary}
                fill="url(#revFill)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashboardChartCard>
  );
}

export function AdminCallsVolumeChart({
  data,
  rangeDays,
  onRangeChange,
  loading,
}: {
  data: { label: string; calls: number }[];
  rangeDays: DateRangeDays;
  onRangeChange: (days: DateRangeDays) => void;
  loading?: boolean;
}) {
  const hasData = data.some((d) => d.calls > 0);

  return (
    <DashboardChartCard
      title="Call volume"
      description="Calls started per day from admin metrics."
      action={
        <DateRangeSelector value={rangeDays} onChange={onRangeChange} />
      }
    >
      {loading ? (
        <ChartSkeleton />
      ) : !hasData ? (
        <ChartEmptyState message="No calls in this period." />
      ) : (
        <div className="h-52 w-full" role="img" aria-label="Call volume over time">
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
                width={32}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar
                dataKey="calls"
                name="Calls"
                fill={CHART_COLORS.secondary}
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

export function TechnicianWorkloadChart({
  data,
  loading,
}: {
  data: WorkloadRow[];
  loading?: boolean;
}) {
  const hasData = data.some((d) => d.assigned > 0 || d.active > 0);

  return (
    <DashboardChartCard
      title="Technician workload"
      description="Assigned and active jobs by technician."
      action={
        <Link
          href="/dispatch"
          className="text-xs font-medium text-brand hover:underline"
        >
          Open dispatch
        </Link>
      }
    >
      {loading ? (
        <ChartSkeleton className="h-44" />
      ) : !hasData ? (
        <ChartEmptyState message="No technician assignments are available." />
      ) : (
        <div
          className="h-44 w-full"
          role="img"
          aria-label="Technician workload"
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 12, left: 4, bottom: 0 }}
            >
              <CartesianGrid stroke={CHART_COLORS.grid} strokeDasharray="3 3" horizontal={false} />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={88}
                tick={{ fill: CHART_COLORS.text, fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend
                wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
                iconType="circle"
                iconSize={8}
              />
              <Bar
                dataKey="assigned"
                name="Assigned"
                fill={CHART_COLORS.tertiary}
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
              />
              <Bar
                dataKey="active"
                name="Active"
                fill={CHART_COLORS.primary}
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashboardChartCard>
  );
}

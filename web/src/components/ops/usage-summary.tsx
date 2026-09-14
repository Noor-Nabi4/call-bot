"use client";

import Link from "next/link";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TenantUsage } from "@/lib/api";
import { billing as copy } from "@/lib/ops-copy";
import { cn } from "@/lib/cn";
import { Surface } from "@/components/ui";
import { CHART_COLORS } from "@/components/ops/charts-shared";

const TRACK = "#e5e7eb";
const WARN = "#f59e0b";
const DANGER = "#dc2626";

function fillColor(used: number, limit: number | null | undefined): string {
  if (limit == null || limit <= 0) return CHART_COLORS.primary;
  const pct = used / limit;
  if (pct > 1) return DANGER;
  if (pct >= 0.85) return WARN;
  return CHART_COLORS.primary;
}

function slotLabel(used: number, limit: number | null | undefined): string {
  if (limit == null) return String(used);
  return `${used} / ${limit}`;
}

function UsageDonut({
  label,
  used,
  limit,
  size = 148,
}: {
  label: string;
  used: number;
  limit: number | null | undefined;
  size?: number;
}) {
  const hasLimit = limit != null && limit > 0;
  const remaining = hasLimit ? Math.max(0, limit - used) : 0;
  const over = hasLimit && used > limit;
  const color = fillColor(used, limit);
  const pct = hasLimit ? Math.min(100, Math.round((used / limit) * 100)) : null;

  const data = hasLimit
    ? [
        { name: "used", value: Math.min(used, limit) },
        { name: "remaining", value: remaining || (used === 0 ? 1 : 0) },
        ...(over ? [{ name: "over", value: used - limit }] : []),
      ]
    : [
        { name: "used", value: Math.max(used, 1) },
        { name: "track", value: Math.max(used, 1) },
      ];

  const colors = hasLimit
    ? over
      ? [DANGER, TRACK, DANGER]
      : [color, TRACK]
    : [color, TRACK];

  return (
    <div className="flex flex-col items-center">
      <div
        className="relative"
        style={{ width: size, height: size }}
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={limit ?? undefined}
        aria-valuenow={used}
      >
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius="68%"
              outerRadius="92%"
              startAngle={90}
              endAngle={-270}
              stroke="none"
              isAnimationActive
            >
              {data.map((entry, i) => (
                <Cell key={entry.name} fill={colors[i] || TRACK} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p
            className={cn(
              "font-mono text-xl font-semibold tabular-nums leading-none",
              over ? "text-danger" : "text-ink",
            )}
          >
            {pct != null ? `${pct}%` : used}
          </p>
          <p className="mt-1 max-w-[6.5rem] truncate text-center font-mono text-[11px] text-text-muted">
            {slotLabel(used, limit)}
          </p>
        </div>
      </div>
      <p className="mt-2 text-xs font-medium text-text-secondary">{label}</p>
    </div>
  );
}

function ResourceBars({ usage }: { usage: TenantUsage }) {
  const rows = [
    {
      name: copy.users,
      used: usage.resources.team_users.used,
      limit: usage.resources.team_users.limit,
    },
    {
      name: copy.numbers,
      used: usage.resources.phone_numbers.used,
      limit: usage.resources.phone_numbers.limit,
    },
    {
      name: copy.knowledge,
      used: usage.resources.knowledge_documents.used,
      limit: usage.resources.knowledge_documents.limit,
    },
    {
      name: copy.concurrent,
      used: usage.resources.concurrent_calls.used,
      limit: usage.resources.concurrent_calls.limit,
    },
  ].map((row) => {
    const limit = row.limit != null && row.limit > 0 ? row.limit : null;
    const pct =
      limit != null
        ? Math.min(100, Math.round((row.used / limit) * 100))
        : Math.min(100, row.used > 0 ? 100 : 0);
    return {
      ...row,
      pct,
      fill: fillColor(row.used, row.limit),
      display: slotLabel(row.used, row.limit),
    };
  });

  return (
    <div className="h-44 w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
        >
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
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
          <Tooltip
            cursor={{ fill: "rgba(15, 118, 110, 0.06)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const row = payload[0].payload as (typeof rows)[number];
              return (
                <div className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs shadow-md">
                  <p className="font-medium text-ink">{row.name}</p>
                  <p className="mt-0.5 font-mono text-text-secondary">
                    {row.display}
                    {row.limit != null ? ` · ${row.pct}%` : ""}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="pct" radius={[0, 6, 6, 0]} barSize={14}>
            {rows.map((row) => (
              <Cell key={row.name} fill={row.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function UsageSummaryPanel({
  usage,
  className,
  compact,
  showBillingLink,
}: {
  usage: TenantUsage;
  className?: string;
  /** Team-focused: seats + voice gauges only */
  compact?: boolean;
  showBillingLink?: boolean;
}) {
  const seats = usage.resources.team_users;

  return (
    <Surface className={cn("p-4", className)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="m-0 text-sm font-semibold text-ink">{copy.usage}</h2>
          <p className="mt-0.5 m-0 text-xs text-text-secondary">
            {copy.usageHint}
          </p>
        </div>
        {showBillingLink ? (
          <Link
            href="/settings/billing"
            className="text-xs font-medium text-brand hover:underline"
          >
            {copy.manage}
          </Link>
        ) : null}
      </div>

      <div
        className={cn(
          "mt-4 grid gap-6",
          compact
            ? "justify-items-center sm:grid-cols-2"
            : "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:items-center",
        )}
      >
        <div
          className={cn(
            "flex flex-wrap items-center justify-center gap-6",
            !compact && "lg:justify-start",
          )}
        >
          <UsageDonut
            label={copy.minutesUsed}
            used={usage.voice_minutes}
            limit={usage.included_minutes}
            size={compact ? 132 : 156}
          />
          <UsageDonut
            label={copy.users}
            used={seats.used}
            limit={seats.limit}
            size={compact ? 132 : 156}
          />
          {!compact ? (
            <UsageDonut
              label={copy.calls}
              used={usage.call_count}
              limit={null}
              size={156}
            />
          ) : null}
        </div>

        {!compact ? (
          <div className="min-w-0">
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-muted">
              {copy.resources}
            </p>
            <ResourceBars usage={usage} />
          </div>
        ) : null}
      </div>

      {!compact && usage.overage_minutes > 0 ? (
        <p className="mt-3 m-0 text-xs text-warn">
          {copy.overage}: {usage.overage_minutes} min
          {usage.estimated_overage_cents != null
            ? ` ($${(usage.estimated_overage_cents / 100).toFixed(2)})`
            : ""}
        </p>
      ) : null}
    </Surface>
  );
}

export function seatsAtLimit(usage: TenantUsage | null): boolean {
  if (!usage) return false;
  const { used, limit } = usage.resources.team_users;
  return limit != null && used >= limit;
}

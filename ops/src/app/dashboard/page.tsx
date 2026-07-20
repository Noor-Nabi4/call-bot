"use client";

import Link from "next/link";
import { CalendarPlus, Plus, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell";
import {
  ActivityFeed,
  AttentionList,
  Panel,
  SummaryStrip,
} from "@/components/ops/dashboard";
import {
  CallsBookingChart,
  JobsActivityChart,
  TechnicianWorkloadChart,
} from "@/components/ops/charts";
import { DistributionPieChart } from "@/components/ops/raffle-charts";
import { CreateJobDrawer } from "@/components/ops/create-job-drawer";
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingSkeleton,
  StatusPill,
  useToast,
} from "@/components/ui";
import { useAuth } from "@/lib/use-auth";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { dashboard as copy } from "@/lib/copy";

function greetingFor(now: Date): string {
  const h = now.getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const router = useRouter();
  const toast = useToast();
  const dash = useDashboardData(user);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-text-secondary">
            {greetingFor(dash.now)}, {user.name.split(" ")[0]}
          </p>
          <h1 className="mt-0.5 font-heading text-3xl font-semibold tracking-tight text-text-primary">
            {user.tenant_name}
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {copy.attentionLead}
          </p>
          <p className="mt-1 text-sm text-text-muted">
            {dash.activeJobs.length} active job
            {dash.activeJobs.length === 1 ? "" : "s"} ·{" "}
            {dash.now.toLocaleDateString(undefined, {
              weekday: "long",
              month: "short",
              day: "numeric",
            })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/customers">
            <Button variant="secondary" size="sm">
              <UserPlus className="size-3.5" aria-hidden />
              Add customer
            </Button>
          </Link>
          <Link href="/appointments">
            <Button variant="secondary" size="sm">
              <CalendarPlus className="size-3.5" aria-hidden />
              Schedule
            </Button>
          </Link>
          <Button size="sm" onClick={() => dash.setJobDrawerOpen(true)}>
            <Plus className="size-3.5" aria-hidden />
            Create job
          </Button>
        </div>
      </header>

      {dash.error ? (
        <ErrorState
          className="mb-4"
          message={dash.error}
          onRetry={dash.retryLoad}
        />
      ) : null}

      {dash.fetching && dash.jobs.length === 0 ? (
        <LoadingSkeleton rows={6} />
      ) : (
        <div className="grid gap-4">
          <SummaryStrip
            items={[
              { label: copy.activeJobs, value: dash.activeJobs.length },
              { label: copy.appointmentsToday, value: dash.apptsToday.length },
              {
                label: copy.availableTechnicians,
                value: dash.availableTechs.length,
              },
              { label: copy.callsToday, value: dash.callsToday.length },
            ]}
          />

          <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <Panel title={copy.needsAttention}>
              <AttentionList items={dash.attention} />
            </Panel>

            <Panel
              title={copy.todaysSchedule}
              action={
                <Link
                  href="/dispatch?view=today"
                  className="text-xs font-medium text-brand hover:underline"
                >
                  {copy.viewAll}
                </Link>
              }
            >
              {dash.todayWork.length === 0 ? (
                <EmptyState
                  className="border-0 py-6"
                  title={copy.noWorkToday}
                  description={copy.noWorkHint}
                />
              ) : (
                <ul className="divide-y divide-border">
                  {dash.todayWork.map((row) => (
                    <li key={row.id}>
                      <Link
                        href={row.href}
                        className="flex items-start justify-between gap-3 py-2.5 transition-colors duration-150 hover:bg-surface-muted/50"
                      >
                        <div className="min-w-0">
                          <p className="text-[10px] font-medium tracking-wide text-text-muted uppercase">
                            {row.kind}
                          </p>
                          <p className="text-sm font-medium text-text-primary">
                            {row.title}
                          </p>
                          <p className="truncate text-xs text-text-secondary">
                            {row.meta}
                          </p>
                        </div>
                        <div className="shrink-0 text-right">
                          {row.status ? (
                            <StatusPill status={row.status} />
                          ) : null}
                          <p className="mt-1 font-mono text-[10px] text-text-muted">
                            {row.when}
                          </p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <JobsActivityChart
              data={dash.jobsActivitySeries}
              rangeDays={dash.chartRange}
              onRangeChange={dash.setChartRange}
              loading={dash.fetching && dash.jobs.length === 0}
            />
            <CallsBookingChart
              data={dash.callsBookingSeries}
              rangeDays={dash.chartRange}
              onRangeChange={dash.setChartRange}
              loading={dash.fetching && dash.jobs.length === 0}
            />
          </div>

          <TechnicianWorkloadChart
            data={dash.technicianWorkload}
            loading={dash.fetching && dash.jobs.length === 0}
          />

          <div className="grid gap-4 lg:grid-cols-2">
            <DistributionPieChart
              title="Jobs by status"
              description={`Job mix for the last ${dash.chartRange} days. Click a slice to open dispatch.`}
              data={dash.jobsByStatusPie}
              loading={dash.fetching && dash.jobs.length === 0}
              onSliceClick={(point) => {
                const status = point.status || point.name.replace(/ /g, "_");
                router.push(`/dispatch?status=${encodeURIComponent(status)}`);
              }}
            />
            <DistributionPieChart
              title="Calls by status"
              description={`Call outcomes for the last ${dash.chartRange} days. Click a slice to open the call log.`}
              data={dash.callsByStatusPie}
              loading={dash.fetching && dash.jobs.length === 0}
              emptyMessage="No call status data is available for this period."
              onSliceClick={(point) => {
                const status = point.status || point.name.replace(/ /g, "_");
                router.push(`/calls?status=${encodeURIComponent(status)}`);
              }}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <Panel title={copy.recentActivity}>
              <ActivityFeed items={dash.activity} />
            </Panel>
            <Panel title="Quick links">
              <div className="flex flex-wrap gap-2">
                <Link
                  href="/dispatch"
                  className="rounded-[10px] border border-border px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
                >
                  Open dispatch
                </Link>
                <Link
                  href="/metrics"
                  className="rounded-[10px] border border-border px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
                >
                  View metrics
                </Link>
                <Link
                  href="/calls"
                  className="rounded-[10px] border border-border px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
                >
                  Call log
                </Link>
              </div>
            </Panel>
          </div>
        </div>
      )}

      <CreateJobDrawer
        open={dash.jobDrawerOpen}
        onClose={() => dash.setJobDrawerOpen(false)}
        form={dash.jobForm}
        onChange={dash.setJobForm}
        onSubmit={(e) => dash.onCreateJob(e, (msg) => toast.push(msg, "success"))}
        busy={dash.formBusy}
        customers={dash.customers}
        formId="dash-job-form"
      />
    </AppShell>
  );
}

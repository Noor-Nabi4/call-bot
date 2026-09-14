"use client";

import Link from "next/link";
import { Suspense } from "react";
import { LayoutGrid, MoreHorizontal, Plus, RefreshCw } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  KanbanBoard,
  KanbanColumn,
  JobCard,
  QuickFilterTabs,
  StatusStrip,
} from "@/components/ops/dispatch";
import { CreateJobDrawer } from "@/components/ops/create-job-drawer";
import { CreateTechDrawer } from "@/components/ops/create-tech-drawer";
import { formatWhen } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/use-auth";
import {
  DISPATCH_SAVED_VIEWS,
  useDispatchBoard,
} from "@/hooks/use-dispatch-board";
import { dispatch as copy, errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  SearchInput,
  Select,
  StatusPill,
  useToast,
} from "@/components/ui";

function DispatchWorkspace() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const toast = useToast();
  const board = useDispatchBoard(user);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0 animate-[ops-rise_280ms_ease-out]">
          <h1 className="font-heading text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">
            {copy.title}
          </h1>
          <p className="mt-0.5 text-sm text-text-secondary">
            {copy.description}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {board.activeJobCount} active job
            {board.activeJobCount === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() =>
              board
                .refresh()
                .catch((e) =>
                  board.setError(safeUserError(e, errors.loadFailed)),
                )
            }
          >
            <RefreshCw className="size-3.5" aria-hidden />
            Refresh
          </Button>
          <Button size="sm" onClick={() => board.setJobDrawerOpen(true)}>
            <Plus className="size-3.5" aria-hidden />
            Create job
          </Button>
        </div>
      </header>

      {board.error ? (
        <ErrorState
          className="mb-3"
          message={board.error}
          onRetry={() => {
            board.setError(null);
            board
              .refresh()
              .catch((e) =>
                board.setError(safeUserError(e, errors.loadFailed)),
              );
          }}
        />
      ) : null}

      <StatusStrip
        columns={board.boardColumns}
        counts={board.statusCounts}
        className="mb-2"
      />

      {board.statusFilter ? (
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-lg border border-border bg-surface-muted px-2.5 py-1 text-text-secondary">
            Status:{" "}
            <span className="font-medium text-text-primary">
              {board.statusFilter.replace(/_/g, " ")}
            </span>
          </span>
          <Link href="/dispatch" className="text-xs text-brand hover:underline">
            Clear status filter
          </Link>
        </div>
      ) : null}

      <div
        className="mb-2 flex flex-wrap items-center gap-2"
        role="toolbar"
        aria-label="Dispatch filters"
      >
        <SearchInput
          className="w-full min-w-[10rem] sm:max-w-[14rem] sm:flex-none"
          placeholder="Search…"
          value={board.search}
          onChange={(e) => board.setSearch(e.target.value)}
          onClear={() => board.setSearch("")}
        />
        <Input
          type="date"
          className="h-8 w-auto min-w-[9.5rem] text-xs"
          value={board.dateFilter}
          onChange={(e) => board.setDateFilter(e.target.value)}
          aria-label="Date"
        />
        <Select
          className="h-8 w-auto min-w-[8rem] text-xs"
          value={board.techFilter}
          onChange={(e) => board.setTechFilter(e.target.value)}
          aria-label="Technician"
        >
          <option value="">Technician</option>
          <option value="unassigned">Unassigned</option>
          {board.techs.map((t) => (
            <option key={t.id} value={t.id}>
              {t.display_name}
            </option>
          ))}
        </Select>
        <div className="relative">
          <Button
            variant="secondary"
            size="sm"
            className={cn(board.moreActive && "border-brand text-brand")}
            aria-expanded={board.moreOpen}
            aria-controls="dispatch-more-filters"
            onClick={() => board.setMoreOpen((v) => !v)}
          >
            <MoreHorizontal className="size-3.5" aria-hidden />
            More Filters
          </Button>
          {board.moreOpen ? (
            <>
              <button
                type="button"
                className="fixed inset-0 z-10 cursor-default"
                aria-label="Close more filters"
                onClick={() => board.setMoreOpen(false)}
              />
              <div
                id="dispatch-more-filters"
                className="absolute top-full left-0 z-20 mt-1 w-64 rounded-xl border border-border bg-surface p-3 shadow-[var(--shadow-elevated)]"
              >
                <div className="grid gap-2">
                  <Field label="Urgency">
                    <Select
                      className="h-8 text-xs"
                      value={board.urgencyFilter}
                      onChange={(e) => board.setUrgencyFilter(e.target.value)}
                    >
                      <option value="">Any</option>
                      <option value="overdue">Overdue</option>
                      <option value="today">Today</option>
                      <option value="upcoming">Upcoming</option>
                      <option value="none">Unscheduled</option>
                    </Select>
                  </Field>
                  <Field label="Area">
                    <Input
                      className="h-8 text-xs"
                      placeholder="Address contains…"
                      value={board.areaFilter}
                      onChange={(e) => board.setAreaFilter(e.target.value)}
                    />
                  </Field>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="justify-start"
                    onClick={() => {
                      board.setMoreOpen(false);
                      board.setTechDrawerOpen(true);
                    }}
                  >
                    Add technician…
                  </Button>
                </div>
              </div>
            </>
          ) : null}
        </div>
        <div className="ml-auto">
          <QuickFilterTabs
            views={[...DISPATCH_SAVED_VIEWS]}
            value={board.savedView}
            onChange={board.setSavedView}
          />
        </div>
      </div>

      {board.fetching && board.jobs.length === 0 ? (
        <LoadingSkeleton rows={5} />
      ) : board.filteredJobs.length === 0 ? (
        <EmptyState
          className="py-10"
          icon={<LayoutGrid className="size-7" />}
          title={copy.noMatch}
          description={copy.noMatchHint}
          action={
            <Button size="sm" onClick={() => board.setJobDrawerOpen(true)}>
              Create job
            </Button>
          }
        />
      ) : (
        <KanbanBoard>
          {board.boardColumns.map((status) => {
            const columnJobs = board.filteredJobs.filter(
              (j) => j.status === status,
            );
            return (
              <KanbanColumn
                key={status}
                status={status}
                count={columnJobs.length}
              >
                {columnJobs.map((job) => (
                  <li key={job.id}>
                    <JobCard
                      job={job}
                      technicians={board.techs}
                      onPreview={board.setPreviewJob}
                      onAssign={(jobId, techId) =>
                        board.onAssign(jobId, techId, (msg) =>
                          toast.push(msg, "success"),
                        )
                      }
                      onDispatch={(jobId) =>
                        board.onDispatch(jobId, (msg) =>
                          toast.push(msg, "success"),
                        )
                      }
                      showAssign={
                        status === "new" ||
                        status === "scheduled" ||
                        status === "dispatched"
                      }
                      showDispatch={
                        status === "scheduled" && !!job.assigned_technician_id
                      }
                    />
                  </li>
                ))}
                {columnJobs.length === 0 ? (
                  <li className="px-1 py-4 text-center text-[11px] text-text-muted">
                    {copy.emptyStage}
                  </li>
                ) : null}
              </KanbanColumn>
            );
          })}
        </KanbanBoard>
      )}

      <DetailDrawer
        open={!!board.previewJob}
        onClose={() => board.setPreviewJob(null)}
        title={board.previewJob?.reference_code || "Job"}
        description={board.previewJob?.service_type}
        footer={
          board.previewJob ? (
            <div className="flex gap-2">
              <Button
                variant="secondary"
                onClick={() => board.setPreviewJob(null)}
              >
                Close
              </Button>
              <Link
                href={`/jobs/${board.previewJob.id}`}
                className="inline-flex"
              >
                <Button>Open full detail</Button>
              </Link>
            </div>
          ) : null
        }
      >
        {board.previewJob ? (
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <StatusPill status={board.previewJob.status} />
              <span className="text-xs text-text-muted">
                {formatWhen(board.previewJob.scheduled_starts_at)}
              </span>
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">
                Customer
              </p>
              <p className="font-medium">
                {board.previewJob.customer?.name || "—"}
              </p>
              {board.previewJob.customer?.address ? (
                <p className="text-text-secondary">
                  {board.previewJob.customer.address}
                </p>
              ) : null}
            </div>
            <div>
              <p className="text-xs font-medium text-text-muted uppercase">
                Technician
              </p>
              <p>
                {board.previewJob.assigned_technician?.display_name ||
                  "Unassigned"}
              </p>
            </div>
          </div>
        ) : null}
      </DetailDrawer>

      <CreateJobDrawer
        open={board.jobDrawerOpen}
        onClose={() => board.setJobDrawerOpen(false)}
        form={board.jobForm}
        onChange={board.setJobForm}
        onSubmit={(e) =>
          board.onCreateJob(e, (msg) => toast.push(msg, "success"))
        }
        busy={board.formBusy}
        customers={board.customers}
        formId="add-job-form"
        emptyHint="No customers yet. Create a customer before adding a job."
      />

      <CreateTechDrawer
        open={board.techDrawerOpen}
        onClose={() => board.setTechDrawerOpen(false)}
        form={board.techForm}
        onChange={board.setTechForm}
        onSubmit={(e) =>
          board.onCreateTech(e, (msg) => toast.push(msg, "success"))
        }
        busy={board.formBusy}
        formId="add-tech-form"
      />
    </AppShell>
  );
}

export default function DispatchPage() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={6} />
        </div>
      }
    >
      <DispatchWorkspace />
    </Suspense>
  );
}

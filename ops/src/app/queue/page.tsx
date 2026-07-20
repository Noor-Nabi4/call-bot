"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ListOrdered } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  claimQueueItem,
  completeQueueItem,
  formatWhen,
  listQueue,
  type QueueItem,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { errors, queue as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  useToast,
  type DataTableColumn,
} from "@/components/ui";

const POLL_MS = 8_000;
const POLL_HIDDEN_MS = 45_000;

type Filter = "open" | "waiting" | "claimed";

export default function QueuePage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const toast = useToast();
  const [items, setItems] = useState<QueueItem[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [fetching, setFetching] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const inFlight = useRef(false);

  const load = useCallback(async (soft = false) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (soft) setRefreshing(true);
    try {
      const data = await listQueue({ limit: 100 });
      setItems(data.items || []);
      setError(null);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      inFlight.current = false;
      setFetching(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    void load(false);
  }, [user, load]);

  useEffect(() => {
    if (!user) return;
    let timeoutId = 0;
    const tick = () => {
      void load(true);
      const ms =
        document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS;
      timeoutId = window.setTimeout(tick, ms);
    };
    timeoutId = window.setTimeout(
      tick,
      document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS,
    );
    const onVis = () => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(
        tick,
        document.visibilityState === "hidden" ? POLL_HIDDEN_MS : POLL_MS,
      );
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      window.clearTimeout(timeoutId);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [user, load]);

  const visible = useMemo(() => {
    return items.filter((item) => {
      if (filter === "waiting") return item.status === "waiting";
      if (filter === "claimed") return item.status === "claimed";
      return item.status === "waiting" || item.status === "claimed";
    });
  }, [items, filter]);

  async function onClaim(id: string) {
    setBusyId(id);
    try {
      const data = await claimQueueItem(id);
      setItems((prev) => prev.map((i) => (i.id === id ? data.item : i)));
      toast.push("Claimed", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusyId(null);
    }
  }

  async function onComplete(id: string, cancel = false) {
    setBusyId(id);
    try {
      const data = await completeQueueItem(id, { cancel });
      setItems((prev) => prev.map((i) => (i.id === id ? data.item : i)));
      toast.push(cancel ? "Cancelled" : "Completed", "success");
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setBusyId(null);
    }
  }

  const columns: DataTableColumn<QueueItem>[] = [
    {
      id: "status",
      header: "Status",
      cell: (i) => <StatusPill status={i.status} />,
      className: "w-28",
    },
    {
      id: "caller",
      header: "Caller",
      cell: (i) => (
        <span className="font-mono text-xs">{i.caller_number || "—"}</span>
      ),
      mono: true,
    },
    {
      id: "reason",
      header: "Reason",
      cell: (i) => <span className="text-sm">{i.reason}</span>,
    },
    {
      id: "created",
      header: "Queued",
      cell: (i) => (
        <span className="text-text-secondary">{formatWhen(i.created_at)}</span>
      ),
    },
    {
      id: "owner",
      header: "Owner",
      cell: (i) => (
        <span className="text-xs text-text-secondary">
          {i.claimed_by || "—"}
        </span>
      ),
    },
    {
      id: "actions",
      header: "",
      cell: (i) => {
        const busy = busyId === i.id;
        if (i.status !== "waiting" && i.status !== "claimed") return null;
        return (
          <div className="flex flex-wrap justify-end gap-2">
            {i.status === "waiting" ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => void onClaim(i.id)}
              >
                {copy.claim}
              </Button>
            ) : null}
            <Button
              size="sm"
              disabled={busy}
              onClick={() => void onComplete(i.id, false)}
            >
              {copy.complete}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => void onComplete(i.id, true)}
            >
              {copy.cancel}
            </Button>
          </div>
        );
      },
    },
  ];

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <div className="flex items-center gap-3">
            {refreshing ? (
              <span className="text-xs text-text-muted">{copy.refreshing}</span>
            ) : null}
            <FilterBar className="mb-0 border-0 bg-transparent p-0">
              <Select
                className="w-auto"
                value={filter}
                onChange={(e) => setFilter(e.target.value as Filter)}
                aria-label="Queue filter"
              >
                <option value="open">{copy.filterAll}</option>
                <option value="waiting">{copy.filterWaiting}</option>
                <option value="claimed">{copy.filterClaimed}</option>
              </Select>
            </FilterBar>
          </div>
        }
      />

      {error ? (
        <ErrorState message={error} onRetry={() => void load(false)} />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={4} />
      ) : (
        <DataTable
          columns={columns}
          rows={visible}
          empty={
            <EmptyState
              icon={<ListOrdered className="size-8" />}
              title={copy.empty}
              description={copy.emptyHint}
            />
          }
        />
      )}
    </AppShell>
  );
}

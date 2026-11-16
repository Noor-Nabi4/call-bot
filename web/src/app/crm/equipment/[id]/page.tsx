"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  getEquipment,
  getEquipmentHistory,
  type EquipmentHistoryItem,
  type EquipmentRow,
} from "@/lib/api/equipment";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

function warrantyHeadline(row: EquipmentRow): string {
  switch (row.warranty_status) {
    case "ACTIVE":
      return "Warranty active";
    case "EXPIRED":
      return "Warranty expired";
    case "NOT_ACTIVE":
      return "Warranty not yet active";
    default:
      return "Warranty unknown";
  }
}

export default function EquipmentDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [row, setRow] = useState<EquipmentRow | null>(null);
  const [history, setHistory] = useState<EquipmentHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [eq, hist] = await Promise.all([
        getEquipment(id),
        getEquipmentHistory(id, { limit: 50 }),
      ]);
      setRow(eq);
      setHistory(hist.history);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={row ? `${row.manufacturer} ${row.model}` : "Equipment"}
        description={row?.serial_number ? `Serial ${row.serial_number}` : undefined}
      />
      <p className="mb-4 text-sm">
        <Link href="/crm/equipment" className="underline-offset-2 hover:underline">
          Back to equipment
        </Link>
        {row?.customer_id ? (
          <>
            {" · "}
            <Link
              href={`/customers/${row.customer_id}`}
              className="underline-offset-2 hover:underline"
            >
              Customer
            </Link>
          </>
        ) : null}
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading || !row ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={row.status} />
              <span className="text-sm font-medium">{warrantyHeadline(row)}</span>
              {row.days_remaining != null && row.warranty_status === "ACTIVE" ? (
                <span className="text-sm text-neutral-600">
                  {row.days_remaining} days remaining
                </span>
              ) : null}
            </div>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-neutral-500">Installation</dt>
                <dd>
                  {row.installation_date
                    ? new Date(row.installation_date).toLocaleDateString()
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Warranty provider</dt>
                <dd>{row.warranty_provider || "—"}</dd>
              </div>
              <div>
                <dt className="text-neutral-500">Warranty end</dt>
                <dd>
                  {row.warranty_end_date
                    ? new Date(row.warranty_end_date).toLocaleDateString()
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Location</dt>
                <dd>{row.location_id ? row.location_id.slice(0, 8) + "…" : "—"}</dd>
              </div>
            </dl>
            {row.warranty_notes ? (
              <p className="text-sm text-neutral-700">{row.warranty_notes}</p>
            ) : null}
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Service history</h2>
            {history.length === 0 ? (
              <p className="text-sm text-neutral-600">No history yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {history.map((item, i) => (
                  <li key={`${item.type}-${item.date}-${i}`} className="border-b border-neutral-200 pb-2">
                    <div className="flex flex-wrap gap-2">
                      <span className="font-medium">{item.type}</span>
                      <span className="text-neutral-500">
                        {new Date(item.date).toLocaleString()}
                      </span>
                    </div>
                    <p>{item.summary}</p>
                    {item.job_id ? (
                      <Link
                        href={`/crm/jobs/${item.job_id}`}
                        className="text-neutral-700 underline-offset-2 hover:underline"
                      >
                        Job {item.job_number || item.job_id.slice(0, 8)}
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import {
  approveEstimate,
  cancelEstimate,
  convertEstimate,
  getEstimate,
  rejectEstimate,
  sendEstimate,
  type EstimateRow,
} from "@/lib/api/estimates";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function EstimateDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [estimate, setEstimate] = useState<EstimateRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id || id === "new") return;
    setLoading(true);
    setError(null);
    try {
      const res = await getEstimate(id);
      setEstimate(res.estimate);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function runAction(fn: () => Promise<EstimateRow>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await fn();
      setEstimate(updated);
    } catch (err) {
      setError(safeUserError(err));
      await load();
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton />
      </div>
    );
  }

  const status = estimate?.status;
  const canSend = status === "DRAFT";
  const canApprove = status === "SENT" || status === "VIEWED";
  const canReject = status === "SENT" || status === "VIEWED";
  const canCancel =
    status === "DRAFT" ||
    status === "SENT" ||
    status === "VIEWED" ||
    status === "APPROVED";
  const canConvert = status === "APPROVED";
  const conversion = estimate?.conversions?.[0];

  return (
    <AppShell user={user}>
      <PageHeader
        title={estimate?.estimate_number || "Estimate"}
        description="Server-authoritative totals and lifecycle. Approval does not create jobs or orders."
      />
      <p className="mb-4 text-sm">
        <Link
          href="/crm/estimates"
          className="underline-offset-2 hover:underline"
        >
          Back to estimates
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading || !estimate ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={estimate.status} />
              <span className="text-sm text-neutral-600">
                {estimate.customer?.display_name ||
                  estimate.customer?.name ||
                  estimate.customer_id}
              </span>
            </div>
            <h2 className="text-lg font-medium">{estimate.title}</h2>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-neutral-500">Valid until</dt>
                <dd>
                  {estimate.valid_until
                    ? new Date(estimate.valid_until).toLocaleString()
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Subtotal</dt>
                <dd>
                  {estimate.subtotal} {estimate.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Discount</dt>
                <dd>
                  {estimate.discount_total} {estimate.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Tax</dt>
                <dd>
                  {estimate.tax_total} {estimate.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Total</dt>
                <dd className="font-medium">
                  {estimate.total} {estimate.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Notes</dt>
                <dd>{estimate.notes || "—"}</dd>
              </div>
            </dl>
            <div className="flex flex-wrap gap-2 pt-2">
              {canSend ? (
                <Button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(async () => (await sendEstimate(id)).estimate)
                  }
                >
                  Send
                </Button>
              ) : null}
              {canApprove ? (
                <Button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(
                      async () => (await approveEstimate(id)).estimate,
                    )
                  }
                >
                  Approve
                </Button>
              ) : null}
              {canReject ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runAction(
                      async () => (await rejectEstimate(id)).estimate,
                    )
                  }
                >
                  Reject
                </Button>
              ) : null}
              {canCancel ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runAction(
                      async () => (await cancelEstimate(id)).estimate,
                    )
                  }
                >
                  Cancel
                </Button>
              ) : null}
              {canConvert ? (
                <>
                  <Button
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Convert this approved estimate to a Job?",
                        )
                      ) {
                        return;
                      }
                      void (async () => {
                        setBusy(true);
                        setError(null);
                        try {
                          const res = await convertEstimate(id, "JOB", id);
                          setEstimate(res.estimate);
                        } catch (err) {
                          setError(safeUserError(err));
                          await load();
                        } finally {
                          setBusy(false);
                        }
                      })();
                    }}
                  >
                    Convert to Job
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => {
                      if (
                        !window.confirm(
                          "Convert product lines on this estimate to an Order?",
                        )
                      ) {
                        return;
                      }
                      void (async () => {
                        setBusy(true);
                        setError(null);
                        try {
                          const res = await convertEstimate(id, "ORDER", id);
                          setEstimate(res.estimate);
                        } catch (err) {
                          setError(safeUserError(err));
                          await load();
                        } finally {
                          setBusy(false);
                        }
                      })();
                    }}
                  >
                    Convert to Order
                  </Button>
                </>
              ) : null}
            </div>
            {conversion ? (
              <p className="text-sm text-neutral-600">
                Converted to {conversion.target_type}{" "}
                {conversion.target_number || conversion.target_id}
                {conversion.target_type === "JOB" ? (
                  <>
                    {" "}
                    (
                    <Link
                      href={`/crm/jobs/${conversion.target_id}`}
                      className="underline-offset-2 hover:underline"
                    >
                      open job
                    </Link>
                    )
                  </>
                ) : (
                  <>
                    {" "}
                    (
                    <Link
                      href={`/crm/orders/${conversion.target_id}`}
                      className="underline-offset-2 hover:underline"
                    >
                      open order
                    </Link>
                    )
                  </>
                )}
              </p>
            ) : null}
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium">Line items</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b text-neutral-500">
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">Item</th>
                    <th className="py-2 pr-3">Qty</th>
                    <th className="py-2 pr-3">Unit</th>
                    <th className="py-2 pr-3">Discount</th>
                    <th className="py-2 pr-3">Tax</th>
                    <th className="py-2">Line total</th>
                  </tr>
                </thead>
                <tbody>
                  {(estimate.items || []).map((item) => (
                    <tr key={item.id} className="border-b border-neutral-100">
                      <td className="py-2 pr-3">{item.item_type}</td>
                      <td className="py-2 pr-3">
                        {item.name_snapshot}
                        {item.sku_snapshot ? (
                          <span className="block text-xs text-neutral-500">
                            {item.sku_snapshot}
                          </span>
                        ) : null}
                      </td>
                      <td className="py-2 pr-3">{item.quantity}</td>
                      <td className="py-2 pr-3">{item.unit_price}</td>
                      <td className="py-2 pr-3">{item.discount_total}</td>
                      <td className="py-2 pr-3">{item.tax_total}</td>
                      <td className="py-2">{item.line_total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-medium">Timeline</h3>
            <ul className="space-y-2 text-sm">
              {(estimate.status_history || []).map((h) => (
                <li key={h.id}>
                  <span className="font-medium">{h.to_status}</span>
                  {h.from_status ? (
                    <span className="text-neutral-500"> from {h.from_status}</span>
                  ) : null}
                  {h.changed_by ? (
                    <span className="text-neutral-500"> · {h.changed_by}</span>
                  ) : null}
                  {h.created_at ? (
                    <span className="text-neutral-500">
                      {" "}
                      · {new Date(h.created_at).toLocaleString()}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </AppShell>
  );
}

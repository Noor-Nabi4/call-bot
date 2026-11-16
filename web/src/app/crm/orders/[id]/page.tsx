"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import {
  archiveOrder,
  cancelOrder,
  getOrder,
  getOrderHistory,
  refundOrder,
  restoreOrder,
  transitionOrder,
  ORDER_CANCELLABLE,
  ORDER_FORWARD_TRANSITIONS,
  type OrderRow,
  type OrderStatusHistoryRow,
} from "@/lib/api/orders";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function OrderDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [order, setOrder] = useState<OrderRow | null>(null);
  const [history, setHistory] = useState<OrderStatusHistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [row, hist] = await Promise.all([
        getOrder(id),
        getOrderHistory(id),
      ]);
      setOrder(row);
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

  async function runAction(fn: () => Promise<OrderRow>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await fn();
      setOrder(updated);
      const hist = await getOrderHistory(id);
      setHistory(hist.history);
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

  const forwards = order
    ? ORDER_FORWARD_TRANSITIONS[order.status] || []
    : [];
  const canCancel = order ? ORDER_CANCELLABLE.has(order.status) : false;
  const canRefund = order?.status === "DELIVERED";

  return (
    <AppShell user={user}>
      <PageHeader
        title={order?.order_number || "Order"}
        description="Lifecycle transitions go through the transition API — status is not freely editable."
      />
      <p className="mb-4 text-sm">
        <Link href="/crm/orders" className="underline-offset-2 hover:underline">
          Back to orders
        </Link>
      </p>
      {error ? <ErrorState message={error} /> : null}
      {loading || !order ? (
        <LoadingSkeleton />
      ) : (
        <div className="space-y-8">
          <section className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={order.status} />
              <span className="text-sm text-neutral-600">
                {order.customer?.display_name || order.customer?.name || order.customer_id}
              </span>
            </div>
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-neutral-500">Subtotal</dt>
                <dd>
                  {order.subtotal} {order.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Discount</dt>
                <dd>
                  {order.discount_total} {order.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Tax</dt>
                <dd>
                  {order.tax_total} {order.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Shipping</dt>
                <dd>
                  {order.shipping_total} {order.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Total</dt>
                <dd className="font-medium">
                  {order.total} {order.currency}
                </dd>
              </div>
              <div>
                <dt className="text-neutral-500">Notes</dt>
                <dd>{order.notes || "—"}</dd>
              </div>
            </dl>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Actions</h2>
            <div className="flex flex-wrap gap-2">
              {forwards.map((to) => (
                <Button
                  key={to}
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      transitionOrder(id, { to_status: to })
                    )
                  }
                >
                  Mark {to}
                </Button>
              ))}
              {canCancel ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      cancelOrder(id, { reason: "Cancelled from CRM" })
                    )
                  }
                >
                  Cancel
                </Button>
              ) : null}
              {canRefund ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void runAction(() =>
                      refundOrder(id, {
                        reason: "Lifecycle refund (payments domain future)",
                      })
                    )
                  }
                >
                  Mark refunded
                </Button>
              ) : null}
              {order.archived_at ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void runAction(() => restoreOrder(id))}
                >
                  Restore
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void runAction(() => archiveOrder(id))}
                >
                  Archive
                </Button>
              )}
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Line items</h2>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-neutral-500">
                  <th className="py-2 pr-2">Product</th>
                  <th className="py-2 pr-2">SKU</th>
                  <th className="py-2 pr-2">Qty</th>
                  <th className="py-2 pr-2">Unit</th>
                  <th className="py-2 pr-2">Disc</th>
                  <th className="py-2 pr-2">Tax</th>
                  <th className="py-2">Line total</th>
                </tr>
              </thead>
              <tbody>
                {(order.items || []).map((item) => (
                  <tr key={item.id} className="border-b border-neutral-100">
                    <td className="py-2 pr-2">
                      {item.product_name_snapshot}
                      {item.variant_name_snapshot
                        ? ` · ${item.variant_name_snapshot}`
                        : ""}
                    </td>
                    <td className="py-2 pr-2">{item.sku_snapshot}</td>
                    <td className="py-2 pr-2">{item.quantity}</td>
                    <td className="py-2 pr-2">{item.unit_price}</td>
                    <td className="py-2 pr-2">{item.discount_total}</td>
                    <td className="py-2 pr-2">{item.tax_total}</td>
                    <td className="py-2">{item.line_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="space-y-2">
            <h2 className="text-base font-medium">Status history</h2>
            <ul className="space-y-2 text-sm">
              {history.map((h) => (
                <li key={h.id} className="border-b border-neutral-100 py-2">
                  <span className="font-medium">
                    {h.from_status || "—"} → {h.to_status}
                  </span>
                  {h.reason ? (
                    <span className="text-neutral-600"> · {h.reason}</span>
                  ) : null}
                  <div className="text-neutral-500">
                    {h.changed_by || "system"}
                    {h.created_at
                      ? ` · ${new Date(h.created_at).toLocaleString()}`
                      : ""}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/shell";
import {
  getInvoice,
  sendInvoice,
  voidInvoice,
  type InvoiceRow,
} from "@/lib/api/invoices";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
  StatusPill,
} from "@/components/ui";

export default function InvoiceDetailPage() {
  const params = useParams();
  const id = String(params.id || "");
  const { user, loading: authLoading } = useAuth();
  const [invoice, setInvoice] = useState<InvoiceRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id || id === "new") return;
    setLoading(true);
    setError(null);
    try {
      const res = await getInvoice(id);
      setInvoice(res.invoice);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function runAction(fn: () => Promise<{ invoice: InvoiceRow }>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fn();
      setInvoice(res.invoice);
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

  const status = invoice?.status;
  const canSend = status === "DRAFT";
  const canVoid =
    status === "DRAFT" ||
    status === "SENT" ||
    status === "PARTIALLY_PAID" ||
    status === "OVERDUE";

  return (
    <AppShell user={user}>
      <PageHeader
        title={invoice?.invoice_number || "Invoice"}
        description="Totals and balance are server authoritative."
      />
      <p className="mb-4 text-sm">
        <Link href="/crm/invoices" className="underline-offset-2 hover:underline">
          Back to invoices
        </Link>
      </p>
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading || !invoice ? (
        <LoadingSkeleton />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <StatusPill status={invoice.status} />
            {canSend ? (
              <Button
                disabled={busy}
                onClick={() => runAction(() => sendInvoice(id))}
              >
                Send
              </Button>
            ) : null}
            {canVoid ? (
              <Button
                variant="danger"
                disabled={busy}
                onClick={() => runAction(() => voidInvoice(id, "voided from admin"))}
              >
                Void
              </Button>
            ) : null}
          </div>
          <dl className="grid gap-2 text-sm md:grid-cols-2">
            <div>
              <dt className="text-text-muted">Customer</dt>
              <dd>{invoice.customer?.name || invoice.customer_id}</dd>
            </div>
            <div>
              <dt className="text-text-muted">Due</dt>
              <dd>
                {invoice.due_date
                  ? new Date(invoice.due_date).toLocaleString()
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">Total</dt>
              <dd>
                {invoice.total_amount} {invoice.currency}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted">Balance</dt>
              <dd>{invoice.balance_due}</dd>
            </div>
          </dl>
          <h2 className="mt-6 text-sm font-semibold">Line items</h2>
          <ul className="mt-2 space-y-2 text-sm">
            {(invoice.items || []).map((item) => (
              <li key={item.id} className="rounded border border-border p-2">
                {item.description} · {item.quantity} × {item.unit_price} ={" "}
                {item.line_total}
              </li>
            ))}
          </ul>
          {invoice.status_history?.length ? (
            <>
              <h2 className="mt-6 text-sm font-semibold">Status history</h2>
              <ul className="mt-2 space-y-1 text-xs text-text-secondary">
                {invoice.status_history.map((h) => (
                  <li key={h.id}>
                    {h.from_status || "—"} → {h.to_status}
                    {h.reason ? ` (${h.reason})` : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </>
      )}
    </AppShell>
  );
}

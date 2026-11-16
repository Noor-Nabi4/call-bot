/** Typed helpers for Stripe invoice payments (Phase 19). */

import { api } from "./client";

export type PaymentRow = {
  id: string;
  invoice_id: string;
  status: string;
  amount: string;
  currency: string;
  refunded_amount: string;
  checkout_url?: string | null;
  applied_to_invoice: boolean;
  created_at?: string | null;
};

export function createPaymentLink(invoiceId: string, amount?: string) {
  return api<{ payment: PaymentRow }>(
    `/api/admin/crm/invoices/${invoiceId}/payment-link`,
    {
      method: "POST",
      body: JSON.stringify(amount ? { amount } : {}),
    },
  );
}

export function listPaymentsForInvoice(invoiceId: string) {
  return api<{ payments: PaymentRow[] }>(
    `/api/admin/crm/payments?invoice_id=${encodeURIComponent(invoiceId)}`,
  );
}

export function getPayment(paymentId: string) {
  return api<{ payment: PaymentRow }>(
    `/api/admin/crm/payments/${paymentId}`,
  );
}

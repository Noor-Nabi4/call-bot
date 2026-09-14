import { Suspense } from "react";
import BillingPage from "./billing-page";

export default function BillingRoute() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-text-muted">Loading…</div>}>
      <BillingPage />
    </Suspense>
  );
}

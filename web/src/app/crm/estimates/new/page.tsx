"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { listCustomers } from "@/lib/api";
import { createEstimate } from "@/lib/api/estimates";
import { listProducts } from "@/lib/api/products";
import { listServices } from "@/lib/api/services";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  ErrorState,
  LoadingSkeleton,
  PageHeader,
} from "@/components/ui";

type CustomerOpt = { id: string; name: string };
type CatalogOpt = { id: string; name: string };

export default function NewEstimatePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [customers, setCustomers] = useState<CustomerOpt[]>([]);
  const [services, setServices] = useState<CatalogOpt[]>([]);
  const [products, setProducts] = useState<CatalogOpt[]>([]);
  const [customerId, setCustomerId] = useState("");
  const [title, setTitle] = useState("Estimate");
  const [itemType, setItemType] = useState<"SERVICE" | "PRODUCT" | "CUSTOM">(
    "SERVICE",
  );
  const [refId, setRefId] = useState("");
  const [customName, setCustomName] = useState("");
  const [customPrice, setCustomPrice] = useState("0.00");
  const [quantity, setQuantity] = useState("1");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading || !user) return;
    void (async () => {
      setLoading(true);
      try {
        const [c, s, p] = await Promise.all([
          listCustomers(),
          listServices({ limit: 100 }),
          listProducts({ limit: 100 }),
        ]);
        setCustomers(
          (c.customers || []).map((row) => ({
            id: row.id,
            name: row.name || row.id,
          })),
        );
        setServices(
          (s.services || []).map((row) => ({
            id: row.id,
            name: row.name,
          })),
        );
        setProducts(
          (p.products || []).map((row) => ({
            id: row.id,
            name: row.name,
          })),
        );
      } catch (err) {
        setError(safeUserError(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [authLoading, user]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !customerId) return;
    setBusy(true);
    setError(null);
    try {
      const item =
        itemType === "SERVICE"
          ? {
              item_type: "SERVICE" as const,
              service_id: refId,
              quantity,
            }
          : itemType === "PRODUCT"
            ? {
                item_type: "PRODUCT" as const,
                product_id: refId,
                quantity,
              }
            : {
                item_type: "CUSTOM" as const,
                name: customName,
                unit_price: customPrice,
                quantity,
              };
      const res = await createEstimate({
        customer_id: customerId,
        title,
        items: [item],
      });
      router.push(`/crm/estimates/${res.estimate.id}`);
    } catch (err) {
      setError(safeUserError(err));
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

  return (
    <AppShell user={user}>
      <PageHeader
        title="New estimate"
        description="Prices resolve on the server from the pricebook/catalog. Client totals are not authoritative."
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
      {loading ? (
        <LoadingSkeleton />
      ) : (
        <form className="max-w-xl space-y-4" onSubmit={(e) => void onSubmit(e)}>
          <label className="block text-sm">
            <span className="text-neutral-600">Customer</span>
            <select
              className="mt-1 w-full rounded border px-3 py-2"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              required
              aria-label="Customer"
            >
              <option value="">Select customer</option>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-neutral-600">Title</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              aria-label="Title"
            />
          </label>
          <label className="block text-sm">
            <span className="text-neutral-600">Line type</span>
            <select
              className="mt-1 w-full rounded border px-3 py-2"
              value={itemType}
              onChange={(e) =>
                setItemType(e.target.value as "SERVICE" | "PRODUCT" | "CUSTOM")
              }
              aria-label="Line type"
            >
              <option value="SERVICE">Service</option>
              <option value="PRODUCT">Product</option>
              <option value="CUSTOM">Custom</option>
            </select>
          </label>
          {itemType === "SERVICE" ? (
            <label className="block text-sm">
              <span className="text-neutral-600">Service</span>
              <select
                className="mt-1 w-full rounded border px-3 py-2"
                value={refId}
                onChange={(e) => setRefId(e.target.value)}
                required
                aria-label="Service"
              >
                <option value="">Select service</option>
                {services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {itemType === "PRODUCT" ? (
            <label className="block text-sm">
              <span className="text-neutral-600">Product</span>
              <select
                className="mt-1 w-full rounded border px-3 py-2"
                value={refId}
                onChange={(e) => setRefId(e.target.value)}
                required
                aria-label="Product"
              >
                <option value="">Select product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {itemType === "CUSTOM" ? (
            <>
              <label className="block text-sm">
                <span className="text-neutral-600">Name</span>
                <input
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  required
                  aria-label="Custom name"
                />
              </label>
              <label className="block text-sm">
                <span className="text-neutral-600">Unit price</span>
                <input
                  className="mt-1 w-full rounded border px-3 py-2"
                  value={customPrice}
                  onChange={(e) => setCustomPrice(e.target.value)}
                  required
                  aria-label="Unit price"
                />
              </label>
            </>
          ) : null}
          <label className="block text-sm">
            <span className="text-neutral-600">Quantity</span>
            <input
              className="mt-1 w-full rounded border px-3 py-2"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
              aria-label="Quantity"
            />
          </label>
          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create draft"}
          </Button>
        </form>
      )}
    </AppShell>
  );
}

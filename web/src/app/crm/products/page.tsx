"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { FolderTree, Package, Plus } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  brandName,
  createProduct,
  getCategoryTree,
  listProducts,
  searchProducts,
  type Product,
  type ProductCategory,
} from "@/lib/api/products";
import { useAuth } from "@/lib/use-auth";
import { errors, products as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  FilterBar,
  ForbiddenState,
  Input,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  Textarea,
  type DataTableColumn,
  useToast,
} from "@/components/ui";

const CREATE_FORM_ID = "create-product-form";

type CreateForm = {
  name: string;
  sku: string;
  description: string;
  category_id: string;
  brand: string;
  price: string;
  cost: string;
  tax_rate: string;
  weight: string;
  weight_unit: string;
  status: string;
};

function emptyCreateForm(): CreateForm {
  return {
    name: "",
    sku: "",
    description: "",
    category_id: "",
    brand: "",
    price: "",
    cost: "",
    tax_rate: "",
    weight: "",
    weight_unit: "KG",
    status: "ACTIVE",
  };
}

function formatUpdated(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function formatMoney(value?: string | null) {
  if (value == null || value === "") return "—";
  return value;
}

function flattenCategories(
  nodes: ProductCategory[],
  depth = 0,
): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = [];
  for (const node of nodes) {
    const prefix = depth > 0 ? `${"— ".repeat(depth)}` : "";
    out.push({ id: node.id, label: `${prefix}${node.name}` });
    if (node.children?.length) {
      out.push(...flattenCategories(node.children, depth + 1));
    }
  }
  return out;
}

export default function ProductsPage() {
  const router = useRouter();
  const { user, loading, forbidden, can } = useAuth({
    permission: "products.read",
  });
  const toast = useToast();
  const canCreate = can("products.create");
  const canUpdate = can("products.update");
  const includeCost = canUpdate;

  const [rows, setRows] = useState<Product[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [archiveFilter, setArchiveFilter] = useState<"active" | "all">(
    "active",
  );
  const [fetching, setFetching] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(emptyCreateForm);
  const [createBusy, setCreateBusy] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(id);
  }, [search]);

  const loadCategories = useCallback(async () => {
    const data = await getCategoryTree();
    setCategories(data.tree || []);
  }, []);

  const load = useCallback(
    async (opts?: { cursor?: string; append?: boolean }) => {
      const params = {
        status: statusFilter || undefined,
        category_id: categoryFilter || undefined,
        include_archived: archiveFilter === "all",
        include_cost: includeCost,
        limit: 50,
        cursor: opts?.cursor,
      };
      const data = debouncedSearch
        ? await searchProducts(debouncedSearch, params)
        : await listProducts({ ...params, q: undefined });
      const products = data.products || [];
      setRows((prev) => (opts?.append ? [...prev, ...products] : products));
      setNextCursor(data.next_cursor ?? null);
    },
    [
      debouncedSearch,
      statusFilter,
      categoryFilter,
      archiveFilter,
      includeCost,
    ],
  );

  useEffect(() => {
    if (!user || forbidden) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setFetching(true);
      setError(null);
      Promise.all([load(), loadCategories()])
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, forbidden, load, loadCategories]);

  async function onLoadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      await load({ cursor: nextCursor, append: true });
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      setLoadingMore(false);
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreateBusy(true);
    setError(null);
    try {
      const name = createForm.name.trim();
      if (!name) throw new Error("Name is required.");
      const { product } = await createProduct(
        {
          name,
          sku: createForm.sku.trim() || null,
          description: createForm.description.trim() || null,
          category_id: createForm.category_id || null,
          brand: createForm.brand.trim() || null,
          price: createForm.price.trim() || null,
          cost: includeCost ? createForm.cost.trim() || null : null,
          tax_rate: createForm.tax_rate.trim() || null,
          weight: createForm.weight.trim() || null,
          weight_unit: createForm.weight.trim()
            ? createForm.weight_unit || "KG"
            : null,
          status: createForm.status || "ACTIVE",
        },
        { include_cost: includeCost },
      );
      toast.push("Product created", "success");
      setCreateOpen(false);
      setCreateForm(emptyCreateForm());
      router.push(`/crm/products/${product.id}`);
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setCreateBusy(false);
    }
  }

  const categoryOptions = flattenCategories(categories);

  const columns: DataTableColumn<Product>[] = [
    {
      id: "name",
      header: "Product",
      cell: (p) => (
        <div>
          <p className="font-medium">
            <Link
              href={`/crm/products/${p.id}`}
              className="hover:text-brand"
              onClick={(e) => e.stopPropagation()}
            >
              {p.name || "Untitled product"}
            </Link>
          </p>
          {p.sku ? (
            <p className="text-xs text-text-muted">SKU {p.sku}</p>
          ) : null}
        </div>
      ),
    },
    {
      id: "category",
      header: "Category",
      cell: (p) => (
        <span className="text-text-secondary">
          {p.category?.name || "—"}
        </span>
      ),
    },
    {
      id: "brand",
      header: "Brand",
      cell: (p) => (
        <span className="text-text-secondary">{brandName(p.brand) || "—"}</span>
      ),
    },
    {
      id: "price",
      header: "Price",
      cell: (p) => (
        <span className="text-text-secondary">{formatMoney(p.price)}</span>
      ),
      className: "w-24",
    },
    ...(includeCost
      ? [
          {
            id: "cost",
            header: "Cost",
            cell: (p: Product) => (
              <span className="text-text-secondary">
                {"cost" in p && p.cost != null ? formatMoney(p.cost) : "—"}
              </span>
            ),
            className: "w-24",
          } satisfies DataTableColumn<Product>,
        ]
      : []),
    {
      id: "status",
      header: "Status",
      cell: (p) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusPill status={p.status} />
          {p.archived_at ? <StatusPill status="archived" /> : null}
        </div>
      ),
      className: "w-36",
    },
    {
      id: "updated",
      header: "Updated",
      cell: (p) => (
        <span className="text-xs text-text-muted">
          {formatUpdated(p.updated_at)}
        </span>
      ),
      className: "w-28",
    },
  ];

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (forbidden) {
    return (
      <AppShell user={user}>
        <ForbiddenState />
      </AppShell>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/crm/categories"
              className="inline-flex h-9 items-center justify-center gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 text-sm font-semibold text-text-primary transition-[background-color,border-color] hover:border-teal/40 hover:bg-teal-soft"
            >
              <FolderTree className="size-4" aria-hidden />
              {copy.categoriesLink}
            </Link>
            {canCreate ? (
              <Button
                onClick={() => {
                  setCreateForm(emptyCreateForm());
                  setCreateOpen(true);
                }}
              >
                <Plus className="size-4" aria-hidden />
                {copy.create}
              </Button>
            ) : null}
          </div>
        }
      />

      <FilterBar>
        <SearchInput
          className="w-full sm:w-64"
          placeholder="Search products…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch("")}
        />
        <Select
          className="w-auto min-w-[8rem]"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Status filter"
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="INACTIVE">Inactive</option>
        </Select>
        <Select
          className="w-auto min-w-[10rem]"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          aria-label="Category filter"
        >
          <option value="">All categories</option>
          {categoryOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </Select>
        <Select
          className="w-auto min-w-[9rem]"
          value={archiveFilter}
          onChange={(e) =>
            setArchiveFilter(e.target.value === "all" ? "all" : "active")
          }
          aria-label="Archive filter"
        >
          <option value="active">Hide archived</option>
          <option value="all">Include archived</option>
        </Select>
      </FilterBar>

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            Promise.all([load(), loadCategories()])
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={rows}
            onRowClick={(p) => router.push(`/crm/products/${p.id}`)}
            empty={
              <EmptyState
                icon={<Package className="size-8" />}
                title={
                  debouncedSearch || statusFilter || categoryFilter
                    ? "No matching products"
                    : copy.empty
                }
                description={
                  debouncedSearch || statusFilter || categoryFilter
                    ? "Try a different search or filter."
                    : copy.emptyHint
                }
              />
            }
          />
          {nextCursor ? (
            <div className="mt-4 flex justify-center">
              <Button
                variant="secondary"
                disabled={loadingMore}
                onClick={() => {
                  void onLoadMore();
                }}
              >
                {loadingMore ? "Loading…" : "Load more"}
              </Button>
            </div>
          ) : null}
        </>
      )}

      <DetailDrawer
        open={createOpen}
        onClose={() => {
          if (createBusy) return;
          setCreateOpen(false);
        }}
        title={copy.create}
        description="Add a catalog product for your business."
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={createBusy}
              onClick={() => setCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form={CREATE_FORM_ID}
              variant="ink"
              disabled={createBusy}
            >
              {createBusy ? "Creating…" : "Create"}
            </Button>
          </div>
        }
      >
        <form id={CREATE_FORM_ID} className="space-y-3" onSubmit={onCreate}>
          <Field label="Name" hint="Required">
            <Input
              value={createForm.name}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, name: e.target.value }))
              }
              placeholder="Product name"
              required
            />
          </Field>
          <Field label="SKU">
            <Input
              value={createForm.sku}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, sku: e.target.value }))
              }
            />
          </Field>
          <Field label="Category">
            <Select
              value={createForm.category_id}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, category_id: e.target.value }))
              }
            >
              <option value="">No category</option>
              {categoryOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Brand">
            <Input
              value={createForm.brand}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, brand: e.target.value }))
              }
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Price">
              <Input
                value={createForm.price}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, price: e.target.value }))
                }
                placeholder="0.00"
              />
            </Field>
            {includeCost ? (
              <Field label="Cost">
                <Input
                  value={createForm.cost}
                  onChange={(e) =>
                    setCreateForm((f) => ({ ...f, cost: e.target.value }))
                  }
                  placeholder="0.00"
                />
              </Field>
            ) : null}
          </div>
          <Field label="Tax rate">
            <Input
              value={createForm.tax_rate}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, tax_rate: e.target.value }))
              }
              placeholder="0.00"
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Weight">
              <Input
                value={createForm.weight}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, weight: e.target.value }))
                }
              />
            </Field>
            <Field label="Weight unit">
              <Select
                value={createForm.weight_unit}
                onChange={(e) =>
                  setCreateForm((f) => ({
                    ...f,
                    weight_unit: e.target.value,
                  }))
                }
              >
                <option value="KG">KG</option>
                <option value="G">G</option>
                <option value="LB">LB</option>
                <option value="OZ">OZ</option>
              </Select>
            </Field>
          </div>
          <Field label="Status">
            <Select
              value={createForm.status}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, status: e.target.value }))
              }
            >
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </Select>
          </Field>
          <Field label="Description">
            <Textarea
              rows={3}
              value={createForm.description}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, description: e.target.value }))
              }
            />
          </Field>
        </form>
      </DetailDrawer>
    </AppShell>
  );
}

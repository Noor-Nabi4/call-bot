"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ImagePlus, Plus, Star, Trash2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  archiveProduct,
  archiveProductImage,
  archiveVariant,
  brandName,
  createVariant,
  getCategoryTree,
  getProduct,
  restoreProduct,
  setPrimaryProductImage,
  updateProduct,
  updateVariant,
  uploadProductImage,
  upsertProductAttribute,
  type Product,
  type ProductCategory,
  type ProductVariant,
} from "@/lib/api/products";
import { useAuth } from "@/lib/use-auth";
import { errors, products as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Breadcrumbs,
  Button,
  ConfirmDialog,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  ForbiddenState,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusPill,
  Surface,
  Textarea,
  useToast,
} from "@/components/ui";

const PROFILE_FORM_ID = "product-profile-form";
const VARIANT_FORM_ID = "product-variant-form";
const ATTRIBUTE_FORM_ID = "product-attribute-form";

type ProfileForm = {
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

type VariantForm = {
  sku: string;
  name: string;
  price: string;
  cost: string;
  status: string;
  stock_on_hand: string;
  attribute_value_ids: string[];
};

type AttributeForm = {
  name: string;
  values: string;
};

function emptyVariantForm(): VariantForm {
  return {
    sku: "",
    name: "",
    price: "",
    cost: "",
    status: "ACTIVE",
    stock_on_hand: "",
    attribute_value_ids: [],
  };
}

function toProfileForm(p: Product): ProfileForm {
  return {
    name: p.name || "",
    sku: p.sku || "",
    description: p.description || "",
    category_id: p.category_id || p.category?.id || "",
    brand: brandName(p.brand),
    price: p.price ?? "",
    cost: p.cost ?? "",
    tax_rate: p.tax_rate ?? "",
    weight: p.weight ?? "",
    weight_unit: p.weight_unit || "KG",
    status: p.status || "ACTIVE",
  };
}

function toVariantForm(v: ProductVariant): VariantForm {
  return {
    sku: v.sku || "",
    name: v.name || "",
    price: v.price ?? "",
    cost: v.cost ?? "",
    status: v.status || "ACTIVE",
    stock_on_hand:
      v.stock_on_hand != null && v.stock_on_hand !== undefined
        ? String(v.stock_on_hand)
        : "",
    attribute_value_ids: (v.attributes || [])
      .map((a) => a.value_id)
      .filter(Boolean),
  };
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

function formatMoney(value?: string | null) {
  if (value == null || value === "") return "—";
  return value;
}

export default function ProductDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, loading, forbidden, can } = useAuth({
    permission: "products.read",
  });
  const toast = useToast();
  const canCreate = can("products.create");
  const canUpdate = can("products.update");
  const canDelete = can("products.delete");
  const includeCost = canUpdate;

  const [product, setProduct] = useState<Product | null>(null);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [profile, setProfile] = useState<ProfileForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saveBusy, setSaveBusy] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveBusy, setArchiveBusy] = useState(false);

  const [variantOpen, setVariantOpen] = useState(false);
  const [editingVariantId, setEditingVariantId] = useState<string | null>(null);
  const [variantForm, setVariantForm] = useState<VariantForm>(emptyVariantForm);
  const [variantBusy, setVariantBusy] = useState(false);
  const [variantArchiveId, setVariantArchiveId] = useState<string | null>(null);
  const [variantArchiveBusy, setVariantArchiveBusy] = useState(false);

  const [attributeOpen, setAttributeOpen] = useState(false);
  const [attributeForm, setAttributeForm] = useState<AttributeForm>({
    name: "",
    values: "",
  });
  const [attributeBusy, setAttributeBusy] = useState(false);

  const [imageBusy, setImageBusy] = useState(false);
  const [imageDeleteId, setImageDeleteId] = useState<string | null>(null);
  const [imageDeleteBusy, setImageDeleteBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [productRes, treeRes] = await Promise.all([
      getProduct(params.id, { include_cost: includeCost }),
      getCategoryTree(),
    ]);
    setProduct(productRes.product);
    setProfile(toProfileForm(productRes.product));
    setCategories(treeRes.tree || []);
  }, [params.id, includeCost]);

  useEffect(() => {
    if (!user || forbidden) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setFetching(true);
      refresh()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, forbidden, refresh]);

  const variants = useMemo(
    () => (product?.variants || []).filter((v) => !v.archived_at),
    [product],
  );
  const images = useMemo(
    () => (product?.images || []).filter((i) => !i.archived_at),
    [product],
  );
  const attributes = product?.attributes || [];
  const categoryOptions = flattenCategories(categories);
  const allAttributeValues = useMemo(
    () =>
      attributes.flatMap((attr) =>
        (attr.values || []).map((v) => ({
          id: v.id,
          label: `${attr.name}: ${v.value}`,
        })),
      ),
    [attributes],
  );

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    if (!product || !profile) return;
    setSaveBusy(true);
    setError(null);
    try {
      const name = profile.name.trim();
      if (!name) throw new Error("Name is required.");
      const { product: updated } = await updateProduct(
        product.id,
        {
          name,
          sku: profile.sku.trim() || null,
          description: profile.description.trim() || null,
          category_id: profile.category_id || null,
          brand: profile.brand.trim() || null,
          price: profile.price.trim() || null,
          cost: includeCost ? profile.cost.trim() || null : undefined,
          tax_rate: profile.tax_rate.trim() || null,
          weight: profile.weight.trim() || null,
          weight_unit: profile.weight.trim()
            ? profile.weight_unit || "KG"
            : null,
          status: profile.status || "ACTIVE",
        },
        { include_cost: includeCost },
      );
      setProduct({
        ...updated,
        variants: updated.variants ?? product.variants,
        attributes: updated.attributes ?? product.attributes,
        images: updated.images ?? product.images,
      });
      setProfile(toProfileForm(updated));
      toast.push("Product updated", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setSaveBusy(false);
    }
  }

  async function onArchive() {
    if (!product) return;
    setArchiveBusy(true);
    setError(null);
    try {
      const { product: updated } = await archiveProduct(product.id);
      setProduct({ ...product, ...updated });
      setProfile(toProfileForm({ ...product, ...updated }));
      setArchiveOpen(false);
      toast.push("Product archived", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setArchiveBusy(false);
    }
  }

  async function onRestore() {
    if (!product) return;
    setArchiveBusy(true);
    setError(null);
    try {
      const { product: updated } = await restoreProduct(product.id, {
        include_cost: includeCost,
      });
      await refresh();
      setProduct((prev) => ({ ...(prev || updated), ...updated }));
      toast.push("Product restored", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setArchiveBusy(false);
    }
  }

  function openCreateVariant() {
    setEditingVariantId(null);
    setVariantForm(emptyVariantForm());
    setVariantOpen(true);
  }

  function openEditVariant(v: ProductVariant) {
    setEditingVariantId(v.id);
    setVariantForm(toVariantForm(v));
    setVariantOpen(true);
  }

  async function onSaveVariant(e: FormEvent) {
    e.preventDefault();
    if (!product) return;
    const sku = variantForm.sku.trim();
    if (!sku) {
      setError("Variant SKU is required.");
      return;
    }
    setVariantBusy(true);
    setError(null);
    try {
      const body = {
        sku,
        name: variantForm.name.trim() || null,
        price: variantForm.price.trim() || null,
        cost: includeCost ? variantForm.cost.trim() || null : undefined,
        status: variantForm.status || "ACTIVE",
        stock_on_hand: (() => {
          const raw = variantForm.stock_on_hand.trim();
          if (!raw) return null;
          const n = Number(raw);
          if (!Number.isFinite(n) || n < 0) {
            throw new Error("Stock on hand must be a non-negative number.");
          }
          return Math.floor(n);
        })(),
        attribute_value_ids: variantForm.attribute_value_ids.length
          ? variantForm.attribute_value_ids
          : null,
      };
      if (editingVariantId) {
        await updateVariant(product.id, editingVariantId, body, {
          include_cost: includeCost,
        });
      } else {
        await createVariant(product.id, body, { include_cost: includeCost });
      }
      setVariantOpen(false);
      await refresh();
      toast.push(
        editingVariantId ? "Variant updated" : "Variant created",
        "success",
      );
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setVariantBusy(false);
    }
  }

  async function onArchiveVariant() {
    if (!product || !variantArchiveId) return;
    setVariantArchiveBusy(true);
    setError(null);
    try {
      await archiveVariant(product.id, variantArchiveId);
      setVariantArchiveId(null);
      await refresh();
      toast.push("Variant archived", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setVariantArchiveBusy(false);
    }
  }

  async function onSaveAttribute(e: FormEvent) {
    e.preventDefault();
    if (!product) return;
    const name = attributeForm.name.trim();
    const values = attributeForm.values
      .split(",")
      .map((v) => v.trim())
      .filter(Boolean);
    if (!name || values.length === 0) {
      setError("Attribute name and at least one value are required.");
      return;
    }
    setAttributeBusy(true);
    setError(null);
    try {
      await upsertProductAttribute(product.id, { name, values });
      setAttributeOpen(false);
      setAttributeForm({ name: "", values: "" });
      await refresh();
      toast.push("Attribute saved", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setAttributeBusy(false);
    }
  }

  async function onUploadImage(file: File | null) {
    if (!product || !file) return;
    setImageBusy(true);
    setError(null);
    try {
      await uploadProductImage(product.id, file, {
        is_primary: images.length === 0,
      });
      await refresh();
      toast.push("Image uploaded", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setImageBusy(false);
    }
  }

  async function onSetPrimaryImage(imageId: string) {
    if (!product) return;
    setError(null);
    try {
      await setPrimaryProductImage(product.id, imageId);
      await refresh();
      toast.push("Primary image updated", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    }
  }

  async function onDeleteImage() {
    if (!product || !imageDeleteId) return;
    setImageDeleteBusy(true);
    setError(null);
    try {
      await archiveProductImage(product.id, imageDeleteId);
      setImageDeleteId(null);
      await refresh();
      toast.push("Image removed", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setImageDeleteBusy(false);
    }
  }

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

  if (fetching) {
    return (
      <AppShell user={user}>
        <LoadingSkeleton rows={8} />
      </AppShell>
    );
  }

  if (!product || !profile) {
    return (
      <AppShell user={user}>
        <EmptyState title={copy.notFound} description="This product may have been removed." />
      </AppShell>
    );
  }

  const showCost = includeCost && "cost" in product;

  return (
    <AppShell user={user}>
      <Breadcrumbs
        items={[
          { label: copy.title, href: "/crm/products" },
          { label: product.name || "Product" },
        ]}
      />
      <PageHeader
        title={product.name || "Product"}
        description={product.sku ? `SKU ${product.sku}` : copy.description}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/crm/products"
              className="inline-flex h-9 items-center justify-center gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 text-sm font-semibold text-text-primary transition-[background-color,border-color] hover:border-teal/40 hover:bg-teal-soft"
            >
              <ArrowLeft className="size-4" aria-hidden />
              Back
            </Link>
            {product.archived_at ? (
              canUpdate ? (
                <Button
                  disabled={archiveBusy}
                  onClick={() => {
                    void onRestore();
                  }}
                >
                  {archiveBusy ? "Restoring…" : "Restore"}
                </Button>
              ) : null
            ) : canDelete ? (
              <Button variant="danger" onClick={() => setArchiveOpen(true)}>
                Archive
              </Button>
            ) : null}
          </div>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusPill status={product.status} />
        {product.archived_at ? <StatusPill status="archived" /> : null}
        {product.category?.name ? (
          <span className="text-sm text-text-muted">
            {product.category.name}
          </span>
        ) : null}
      </div>

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Surface className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">Overview</h2>
            {canUpdate ? (
              <Button
                type="submit"
                form={PROFILE_FORM_ID}
                size="sm"
                disabled={saveBusy}
              >
                {saveBusy ? "Saving…" : "Save"}
              </Button>
            ) : null}
          </div>
          <form
            id={PROFILE_FORM_ID}
            className="space-y-3"
            onSubmit={onSaveProfile}
          >
            <Field label="Name">
              <Input
                value={profile.name}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, name: e.target.value } : f))
                }
              />
            </Field>
            <Field label="SKU">
              <Input
                value={profile.sku}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, sku: e.target.value } : f))
                }
              />
            </Field>
            <Field label="Category">
              <Select
                value={profile.category_id}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) =>
                    f ? { ...f, category_id: e.target.value } : f,
                  )
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
                value={profile.brand}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, brand: e.target.value } : f))
                }
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Price">
                <Input
                  value={profile.price}
                  disabled={!canUpdate}
                  onChange={(e) =>
                    setProfile((f) =>
                      f ? { ...f, price: e.target.value } : f,
                    )
                  }
                />
              </Field>
              {showCost ? (
                <Field label="Cost">
                  <Input
                    value={profile.cost}
                    disabled={!canUpdate}
                    onChange={(e) =>
                      setProfile((f) =>
                        f ? { ...f, cost: e.target.value } : f,
                      )
                    }
                  />
                </Field>
              ) : null}
            </div>
            <Field label="Tax rate">
              <Input
                value={profile.tax_rate}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) =>
                    f ? { ...f, tax_rate: e.target.value } : f,
                  )
                }
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Weight">
                <Input
                  value={profile.weight}
                  disabled={!canUpdate}
                  onChange={(e) =>
                    setProfile((f) =>
                      f ? { ...f, weight: e.target.value } : f,
                    )
                  }
                />
              </Field>
              <Field label="Weight unit">
                <Select
                  value={profile.weight_unit}
                  disabled={!canUpdate}
                  onChange={(e) =>
                    setProfile((f) =>
                      f ? { ...f, weight_unit: e.target.value } : f,
                    )
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
                value={profile.status}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) =>
                    f ? { ...f, status: e.target.value } : f,
                  )
                }
              >
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </Select>
            </Field>
            <Field label="Description">
              <Textarea
                rows={4}
                value={profile.description}
                disabled={!canUpdate}
                onChange={(e) =>
                  setProfile((f) =>
                    f ? { ...f, description: e.target.value } : f,
                  )
                }
              />
            </Field>
          </form>
        </Surface>

        <div className="space-y-4">
          <Surface className="space-y-3 p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Images</h2>
              {canUpdate ? (
                <label className="inline-flex cursor-pointer items-center gap-1.5 text-sm font-semibold text-teal">
                  <ImagePlus className="size-4" aria-hidden />
                  {imageBusy ? "Uploading…" : "Upload"}
                  <input
                    type="file"
                    accept="image/*"
                    className="sr-only"
                    disabled={imageBusy}
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null;
                      e.target.value = "";
                      void onUploadImage(file);
                    }}
                  />
                </label>
              ) : null}
            </div>
            {images.length === 0 ? (
              <EmptyState
                title="No images"
                description="Upload a product photo to show in the catalog."
              />
            ) : (
              <ul className="grid grid-cols-2 gap-3">
                {images.map((img) => (
                  <li
                    key={img.id}
                    className="relative overflow-hidden rounded-[var(--radius-md)] border border-border bg-surface-muted"
                  >
                    {img.download_url ? (
                      <img
                        src={img.download_url}
                        alt={img.alt_text || product.name}
                        className="aspect-square w-full object-cover"
                      />
                    ) : (
                      <div className="flex aspect-square items-center justify-center text-xs text-text-muted">
                        No preview
                      </div>
                    )}
                    <div className="flex items-center justify-between gap-1 p-2">
                      {img.is_primary ? (
                        <StatusPill status="primary" />
                      ) : canUpdate ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            void onSetPrimaryImage(img.id);
                          }}
                        >
                          <Star className="size-3.5" aria-hidden />
                          Primary
                        </Button>
                      ) : (
                        <span />
                      )}
                      {canDelete ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setImageDeleteId(img.id)}
                          aria-label="Delete image"
                        >
                          <Trash2 className="size-3.5" aria-hidden />
                        </Button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Surface>

          <Surface className="space-y-3 p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">Attributes</h2>
              {canUpdate ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setAttributeForm({ name: "", values: "" });
                    setAttributeOpen(true);
                  }}
                >
                  <Plus className="size-4" aria-hidden />
                  Add
                </Button>
              ) : null}
            </div>
            {attributes.length === 0 ? (
              <p className="text-sm text-text-muted">
                No attributes yet. Add options like Size or Color for variants.
              </p>
            ) : (
              <ul className="space-y-2">
                {attributes.map((attr) => (
                  <li
                    key={attr.id}
                    className="rounded-[var(--radius-md)] border border-border px-3 py-2"
                  >
                    <p className="text-sm font-medium">{attr.name}</p>
                    <p className="text-xs text-text-muted">
                      {(attr.values || []).map((v) => v.value).join(", ") ||
                        "—"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Surface>
        </div>
      </div>

      <Surface className="mt-4 space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Variants</h2>
          {canCreate ? (
            <Button size="sm" onClick={openCreateVariant}>
              <Plus className="size-4" aria-hidden />
              Add variant
            </Button>
          ) : null}
        </div>
        {variants.length === 0 ? (
          <EmptyState
            title="No variants"
            description="Create variants when this product has multiple SKUs."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <thead className="text-xs text-text-muted">
                <tr className="border-b border-border">
                  <th className="py-2 pr-3 font-medium">SKU</th>
                  <th className="py-2 pr-3 font-medium">Name</th>
                  <th className="py-2 pr-3 font-medium">Price</th>
                  {showCost ? (
                    <th className="py-2 pr-3 font-medium">Cost</th>
                  ) : null}
                  <th className="py-2 pr-3 font-medium">Stock</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {variants.map((v) => (
                  <tr key={v.id} className="border-b border-border/70">
                    <td className="py-2.5 pr-3 font-medium">{v.sku}</td>
                    <td className="py-2.5 pr-3 text-text-secondary">
                      {v.name || "—"}
                      {v.attributes?.length ? (
                        <p className="text-xs text-text-muted">
                          {v.attributes
                            .map((a) => `${a.attribute_name}: ${a.value}`)
                            .join(" · ")}
                        </p>
                      ) : null}
                    </td>
                    <td className="py-2.5 pr-3 text-text-secondary">
                      {formatMoney(v.effective_price ?? v.price)}
                    </td>
                    {showCost ? (
                      <td className="py-2.5 pr-3 text-text-secondary">
                        {"cost" in v ? formatMoney(v.cost) : "—"}
                      </td>
                    ) : null}
                    <td className="py-2.5 pr-3 text-text-secondary">
                      {v.stock_on_hand ?? "—"}
                    </td>
                    <td className="py-2.5 pr-3">
                      <StatusPill status={v.status} />
                    </td>
                    <td className="py-2.5">
                      <div className="flex flex-wrap gap-1.5">
                        {canUpdate ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => openEditVariant(v)}
                          >
                            Edit
                          </Button>
                        ) : null}
                        {canDelete ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setVariantArchiveId(v.id)}
                          >
                            Archive
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Surface>

      <DetailDrawer
        open={variantOpen}
        onClose={() => {
          if (variantBusy) return;
          setVariantOpen(false);
        }}
        title={editingVariantId ? "Edit variant" : "New variant"}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={variantBusy}
              onClick={() => setVariantOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form={VARIANT_FORM_ID}
              variant="ink"
              disabled={variantBusy}
            >
              {variantBusy ? "Saving…" : "Save"}
            </Button>
          </div>
        }
      >
        <form
          id={VARIANT_FORM_ID}
          className="space-y-3"
          onSubmit={onSaveVariant}
        >
          <Field label="SKU" hint="Required">
            <Input
              value={variantForm.sku}
              onChange={(e) =>
                setVariantForm((f) => ({ ...f, sku: e.target.value }))
              }
              required
            />
          </Field>
          <Field label="Name">
            <Input
              value={variantForm.name}
              onChange={(e) =>
                setVariantForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Price">
              <Input
                value={variantForm.price}
                onChange={(e) =>
                  setVariantForm((f) => ({ ...f, price: e.target.value }))
                }
              />
            </Field>
            {includeCost ? (
              <Field label="Cost">
                <Input
                  value={variantForm.cost}
                  onChange={(e) =>
                    setVariantForm((f) => ({ ...f, cost: e.target.value }))
                  }
                />
              </Field>
            ) : null}
          </div>
          <Field label="Stock on hand">
            <Input
              type="number"
              min={0}
              value={variantForm.stock_on_hand}
              onChange={(e) =>
                setVariantForm((f) => ({
                  ...f,
                  stock_on_hand: e.target.value,
                }))
              }
            />
          </Field>
          <Field label="Status">
            <Select
              value={variantForm.status}
              onChange={(e) =>
                setVariantForm((f) => ({ ...f, status: e.target.value }))
              }
            >
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </Select>
          </Field>
          {allAttributeValues.length ? (
            <Field label="Attribute values">
              <div className="max-h-40 space-y-1.5 overflow-y-auto rounded-[var(--radius-md)] border border-border p-2">
                {allAttributeValues.map((v) => {
                  const checked = variantForm.attribute_value_ids.includes(
                    v.id,
                  );
                  return (
                    <label
                      key={v.id}
                      className="flex cursor-pointer items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setVariantForm((f) => ({
                            ...f,
                            attribute_value_ids: checked
                              ? f.attribute_value_ids.filter((id) => id !== v.id)
                              : [...f.attribute_value_ids, v.id],
                          }));
                        }}
                      />
                      {v.label}
                    </label>
                  );
                })}
              </div>
            </Field>
          ) : null}
        </form>
      </DetailDrawer>

      <DetailDrawer
        open={attributeOpen}
        onClose={() => {
          if (attributeBusy) return;
          setAttributeOpen(false);
        }}
        title="Add attribute"
        description="Upserts by name. Comma-separate values."
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={attributeBusy}
              onClick={() => setAttributeOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form={ATTRIBUTE_FORM_ID}
              variant="ink"
              disabled={attributeBusy}
            >
              {attributeBusy ? "Saving…" : "Save"}
            </Button>
          </div>
        }
      >
        <form
          id={ATTRIBUTE_FORM_ID}
          className="space-y-3"
          onSubmit={onSaveAttribute}
        >
          <Field label="Name" hint="e.g. Size">
            <Input
              value={attributeForm.name}
              onChange={(e) =>
                setAttributeForm((f) => ({ ...f, name: e.target.value }))
              }
              required
            />
          </Field>
          <Field label="Values" hint="Comma-separated, e.g. S, M, L">
            <Input
              value={attributeForm.values}
              onChange={(e) =>
                setAttributeForm((f) => ({ ...f, values: e.target.value }))
              }
              required
            />
          </Field>
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={archiveOpen}
        onCancel={() => setArchiveOpen(false)}
        title="Archive product?"
        description="Archived products are hidden from the default catalog list. You can restore them later."
        confirmLabel={archiveBusy ? "Archiving…" : "Archive"}
        danger
        busy={archiveBusy}
        onConfirm={() => {
          void onArchive();
        }}
      />

      <ConfirmDialog
        open={Boolean(variantArchiveId)}
        onCancel={() => setVariantArchiveId(null)}
        title="Archive variant?"
        description="This removes the variant from the active catalog."
        confirmLabel={variantArchiveBusy ? "Archiving…" : "Archive"}
        danger
        busy={variantArchiveBusy}
        onConfirm={() => {
          void onArchiveVariant();
        }}
      />

      <ConfirmDialog
        open={Boolean(imageDeleteId)}
        onCancel={() => setImageDeleteId(null)}
        title="Remove image?"
        description="This archives the image from the product."
        confirmLabel={imageDeleteBusy ? "Removing…" : "Remove"}
        danger
        busy={imageDeleteBusy}
        onConfirm={() => {
          void onDeleteImage();
        }}
      />
    </AppShell>
  );
}

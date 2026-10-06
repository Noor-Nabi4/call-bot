/** Typed helpers for Product Catalog admin APIs. */

import { api, API_BASE } from "./client";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";

export type CatalogStatus = "ACTIVE" | "INACTIVE";

export type ProductBrand = {
  id: string;
  name: string;
  archived_at?: string | null;
};

export type ProductCategory = {
  id: string;
  name: string;
  slug?: string | null;
  description?: string | null;
  parent_id?: string | null;
  status: CatalogStatus | string;
  sort_order?: number;
  product_count?: number;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  children?: ProductCategory[];
};

export type ProductAttributeValue = {
  id: string;
  value: string;
  sort_order?: number;
};

export type ProductAttribute = {
  id: string;
  name: string;
  sort_order?: number;
  values: ProductAttributeValue[];
};

export type VariantAttributeLink = {
  attribute_id?: string | null;
  attribute_name?: string | null;
  value_id: string;
  value: string;
};

export type ProductVariant = {
  id: string;
  product_id: string;
  sku: string;
  name?: string | null;
  price?: string | null;
  effective_price?: string | null;
  cost?: string | null;
  effective_cost?: string | null;
  status: CatalogStatus | string;
  stock_on_hand?: number | null;
  inventory_item_id?: string | null;
  attributes?: VariantAttributeLink[];
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProductImage = {
  id: string;
  product_id: string;
  variant_id?: string | null;
  content_type?: string | null;
  file_size?: number | null;
  width?: number | null;
  height?: number | null;
  alt_text?: string | null;
  sort_order?: number;
  is_primary: boolean;
  download_url?: string | null;
  archived_at?: string | null;
  created_at?: string | null;
};

export type Product = {
  id: string;
  name: string;
  sku?: string | null;
  description?: string | null;
  category_id?: string | null;
  category?: ProductCategory | null;
  brand_id?: string | null;
  brand?: ProductBrand | string | null;
  price?: string | null;
  cost?: string | null;
  tax_rate?: string | null;
  weight?: string | null;
  weight_unit?: string | null;
  status: CatalogStatus | string;
  has_variants?: boolean;
  variants?: ProductVariant[];
  attributes?: ProductAttribute[];
  images?: ProductImage[];
  archived_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ProductListParams = {
  q?: string;
  status?: string;
  category_id?: string;
  brand_id?: string;
  include_archived?: boolean;
  min_price?: string;
  max_price?: string;
  has_variants?: boolean;
  include_cost?: boolean;
  limit?: number;
  cursor?: string;
};

export type ProductListResponse = {
  products: Product[];
  next_cursor?: string | null;
  limit?: number;
};

export type ProductCreateBody = {
  name: string;
  sku?: string | null;
  description?: string | null;
  category_id?: string | null;
  brand?: string | null;
  brand_id?: string | null;
  price?: string | number | null;
  cost?: string | number | null;
  tax_rate?: string | number | null;
  weight?: string | number | null;
  weight_unit?: string | null;
  status?: string | null;
};

export type ProductUpdateBody = {
  name?: string | null;
  sku?: string | null;
  description?: string | null;
  category_id?: string | null;
  brand?: string | null;
  brand_id?: string | null;
  price?: string | number | null;
  cost?: string | number | null;
  tax_rate?: string | number | null;
  weight?: string | number | null;
  weight_unit?: string | null;
  status?: string | null;
};

export type CategoryCreateBody = {
  name: string;
  description?: string | null;
  parent_id?: string | null;
  status?: string | null;
  sort_order?: number | null;
};

export type CategoryUpdateBody = {
  name?: string | null;
  description?: string | null;
  parent_id?: string | null;
  status?: string | null;
  sort_order?: number | null;
};

export type CategoryArchiveBody = {
  reassign_to_category_id?: string | null;
  reassign_products?: boolean;
};

export type VariantCreateBody = {
  sku: string;
  name?: string | null;
  price?: string | number | null;
  cost?: string | number | null;
  status?: string | null;
  stock_on_hand?: number | null;
  inventory_item_id?: string | null;
  attribute_value_ids?: string[] | null;
};

export type VariantUpdateBody = {
  sku?: string | null;
  name?: string | null;
  price?: string | number | null;
  cost?: string | number | null;
  status?: string | null;
  stock_on_hand?: number | null;
  inventory_item_id?: string | null;
  attribute_value_ids?: string[] | null;
};

export type AttributeUpsertBody = {
  name: string;
  values: string[];
  sort_order?: number;
};

const BASE = "/api/admin/crm";
const PRODUCTS = `${BASE}/products`;
const CATEGORIES = `${BASE}/categories`;

function productQuery(opts?: ProductListParams): string {
  const params = new URLSearchParams();
  if (opts?.q) params.set("q", opts.q);
  if (opts?.status) params.set("status", opts.status);
  if (opts?.category_id) params.set("category_id", opts.category_id);
  if (opts?.brand_id) params.set("brand_id", opts.brand_id);
  if (opts?.include_archived) params.set("include_archived", "true");
  if (opts?.min_price) params.set("min_price", opts.min_price);
  if (opts?.max_price) params.set("max_price", opts.max_price);
  if (opts?.has_variants != null) {
    params.set("has_variants", opts.has_variants ? "true" : "false");
  }
  if (opts?.include_cost) params.set("include_cost", "true");
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.cursor) params.set("cursor", opts.cursor);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

function costQuery(includeCost?: boolean): string {
  return includeCost ? "?include_cost=true" : "";
}

/** Multipart upload helper — omits JSON Content-Type so the browser sets the boundary. */
async function apiMultipart<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    let message: string = errors.generic;
    let code: string | undefined;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) message = detail.message;
      if (typeof detail === "object" && detail?.code) code = detail.code;
    } catch {
      /* ignore */
    }
    if (code === "subscription_required" && typeof window !== "undefined") {
      const pathNow = window.location.pathname;
      if (!pathNow.startsWith("/settings/billing")) {
        window.location.assign("/settings/billing");
      }
    }
    throw new Error(safeUserError(message, errors.generic));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function brandName(brand?: ProductBrand | string | null): string {
  if (!brand) return "";
  if (typeof brand === "string") return brand;
  return brand.name || "";
}

// --- Products ---

export function listProducts(opts?: ProductListParams) {
  return api<ProductListResponse>(`${PRODUCTS}${productQuery(opts)}`);
}

export function searchProducts(q: string, opts?: Omit<ProductListParams, "q">) {
  return api<ProductListResponse>(
    `${PRODUCTS}/search${productQuery({ ...opts, q })}`,
  );
}

export function getProduct(productId: string, opts?: { include_cost?: boolean }) {
  return api<{ product: Product }>(
    `${PRODUCTS}/${productId}${costQuery(opts?.include_cost)}`,
  );
}

export function createProduct(
  body: ProductCreateBody,
  opts?: { include_cost?: boolean },
) {
  return api<{ product: Product }>(`${PRODUCTS}${costQuery(opts?.include_cost)}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateProduct(
  productId: string,
  body: ProductUpdateBody,
  opts?: { include_cost?: boolean },
) {
  return api<{ product: Product }>(
    `${PRODUCTS}/${productId}${costQuery(opts?.include_cost)}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export function archiveProduct(productId: string) {
  return api<{ product: Product }>(`${PRODUCTS}/${productId}`, {
    method: "DELETE",
  });
}

export function restoreProduct(
  productId: string,
  opts?: { include_cost?: boolean },
) {
  return api<{ product: Product }>(
    `${PRODUCTS}/${productId}/restore${costQuery(opts?.include_cost)}`,
    { method: "POST" },
  );
}

// --- Variants ---

export function listVariants(
  productId: string,
  opts?: { include_archived?: boolean; include_cost?: boolean },
) {
  const params = new URLSearchParams();
  if (opts?.include_archived) params.set("include_archived", "true");
  if (opts?.include_cost) params.set("include_cost", "true");
  const qs = params.toString();
  return api<{ variants: ProductVariant[] }>(
    `${PRODUCTS}/${productId}/variants${qs ? `?${qs}` : ""}`,
  );
}

export function createVariant(
  productId: string,
  body: VariantCreateBody,
  opts?: { include_cost?: boolean },
) {
  return api<{ variant: ProductVariant }>(
    `${PRODUCTS}/${productId}/variants${costQuery(opts?.include_cost)}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

export function updateVariant(
  productId: string,
  variantId: string,
  body: VariantUpdateBody,
  opts?: { include_cost?: boolean },
) {
  return api<{ variant: ProductVariant }>(
    `${PRODUCTS}/${productId}/variants/${variantId}${costQuery(opts?.include_cost)}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    },
  );
}

export function archiveVariant(productId: string, variantId: string) {
  return api<{ variant: ProductVariant }>(
    `${PRODUCTS}/${productId}/variants/${variantId}`,
    { method: "DELETE" },
  );
}

// --- Attributes ---

export function upsertProductAttribute(
  productId: string,
  body: AttributeUpsertBody,
) {
  return api<{ attribute: ProductAttribute }>(
    `${PRODUCTS}/${productId}/attributes`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

// --- Images ---

export function listProductImages(
  productId: string,
  opts?: { variant_id?: string; include_archived?: boolean },
) {
  const params = new URLSearchParams();
  if (opts?.variant_id) params.set("variant_id", opts.variant_id);
  if (opts?.include_archived) params.set("include_archived", "true");
  const qs = params.toString();
  return api<{ images: ProductImage[] }>(
    `${PRODUCTS}/${productId}/images${qs ? `?${qs}` : ""}`,
  );
}

export function uploadProductImage(
  productId: string,
  file: File,
  opts?: { alt_text?: string; variant_id?: string; is_primary?: boolean },
) {
  const form = new FormData();
  form.append("file", file);
  if (opts?.alt_text) form.append("alt_text", opts.alt_text);
  if (opts?.variant_id) form.append("variant_id", opts.variant_id);
  if (opts?.is_primary) form.append("is_primary", "true");
  return apiMultipart<{ image: ProductImage }>(
    `${PRODUCTS}/${productId}/images`,
    form,
  );
}

export function setPrimaryProductImage(productId: string, imageId: string) {
  return api<{ image: ProductImage }>(
    `${PRODUCTS}/${productId}/images/${imageId}/primary`,
    { method: "POST" },
  );
}

export function archiveProductImage(productId: string, imageId: string) {
  return api<{ image: ProductImage }>(
    `${PRODUCTS}/${productId}/images/${imageId}`,
    { method: "DELETE" },
  );
}

// --- Categories ---

export function listCategories(opts?: {
  include_archived?: boolean;
  parent_id?: string;
}) {
  const params = new URLSearchParams();
  if (opts?.include_archived) params.set("include_archived", "true");
  if (opts?.parent_id) params.set("parent_id", opts.parent_id);
  const qs = params.toString();
  return api<{ categories: ProductCategory[] }>(
    `${CATEGORIES}${qs ? `?${qs}` : ""}`,
  );
}

export function getCategoryTree() {
  return api<{ tree: ProductCategory[] }>(`${CATEGORIES}/tree`);
}

export function getCategory(categoryId: string) {
  return api<{ category: ProductCategory }>(`${CATEGORIES}/${categoryId}`);
}

export function createCategory(body: CategoryCreateBody) {
  return api<{ category: ProductCategory }>(CATEGORIES, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateCategory(categoryId: string, body: CategoryUpdateBody) {
  return api<{ category: ProductCategory }>(`${CATEGORIES}/${categoryId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function archiveCategory(
  categoryId: string,
  body?: CategoryArchiveBody,
) {
  return api<{ category: ProductCategory }>(`${CATEGORIES}/${categoryId}`, {
    method: "DELETE",
    body: body ? JSON.stringify(body) : undefined,
  });
}

export function restoreCategory(categoryId: string) {
  return api<{ category: ProductCategory }>(
    `${CATEGORIES}/${categoryId}/restore`,
    { method: "POST" },
  );
}

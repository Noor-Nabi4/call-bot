"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ChevronRight, FolderTree, Package, Plus } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  archiveCategory,
  createCategory,
  getCategoryTree,
  type ProductCategory,
} from "@/lib/api/products";
import { useAuth } from "@/lib/use-auth";
import { errors, productCategories as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
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

const CREATE_FORM_ID = "create-category-form";

type CreateForm = {
  name: string;
  description: string;
  parent_id: string;
  status: string;
};

function emptyCreateForm(parentId = ""): CreateForm {
  return {
    name: "",
    description: "",
    parent_id: parentId,
    status: "ACTIVE",
  };
}

function flattenForSelect(
  nodes: ProductCategory[],
  depth = 0,
  excludeId?: string,
): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = [];
  for (const node of nodes) {
    if (node.id === excludeId) continue;
    const prefix = depth > 0 ? `${"— ".repeat(depth)}` : "";
    out.push({ id: node.id, label: `${prefix}${node.name}` });
    if (node.children?.length) {
      out.push(...flattenForSelect(node.children, depth + 1, excludeId));
    }
  }
  return out;
}

function CategoryNode({
  node,
  depth,
  canCreate,
  canDelete,
  onAddChild,
  onArchive,
}: {
  node: ProductCategory;
  depth: number;
  canCreate: boolean;
  canDelete: boolean;
  onAddChild: (parentId: string) => void;
  onArchive: (id: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const children = node.children || [];
  const hasChildren = children.length > 0;

  return (
    <li>
      <div
        className="flex items-center gap-2 rounded-[var(--radius-md)] border border-border px-3 py-2"
        style={{ marginLeft: depth * 16 }}
      >
        <button
          type="button"
          className="rounded p-0.5 text-text-muted hover:bg-surface-muted disabled:opacity-40"
          disabled={!hasChildren}
          aria-label={open ? "Collapse" : "Expand"}
          onClick={() => setOpen((v) => !v)}
        >
          <ChevronRight
            className={`size-4 transition-transform ${open && hasChildren ? "rotate-90" : ""}`}
            aria-hidden
          />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium">{node.name}</p>
            <StatusPill status={node.status} />
            {typeof node.product_count === "number" ? (
              <span className="text-xs text-text-muted">
                {node.product_count} product
                {node.product_count === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>
          {node.description ? (
            <p className="truncate text-xs text-text-muted">
              {node.description}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          {canCreate ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onAddChild(node.id)}
            >
              <Plus className="size-3.5" aria-hidden />
              {copy.createChild}
            </Button>
          ) : null}
          {canDelete ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onArchive(node.id)}
            >
              Archive
            </Button>
          ) : null}
        </div>
      </div>
      {open && hasChildren ? (
        <ul className="mt-2 space-y-2">
          {children.map((child) => (
            <CategoryNode
              key={child.id}
              node={child}
              depth={depth + 1}
              canCreate={canCreate}
              canDelete={canDelete}
              onAddChild={onAddChild}
              onArchive={onArchive}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function findCategory(
  nodes: ProductCategory[],
  id: string,
): ProductCategory | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children?.length) {
      const found = findCategory(node.children, id);
      if (found) return found;
    }
  }
  return null;
}

export default function CategoriesPage() {
  const { user, loading, forbidden, can } = useAuth({
    permission: "products.read",
  });
  const toast = useToast();
  const canCreate = can("products.create");
  const canDelete = can("products.delete");

  const [tree, setTree] = useState<ProductCategory[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(emptyCreateForm);
  const [createBusy, setCreateBusy] = useState(false);

  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [archiveReassignTo, setArchiveReassignTo] = useState("");
  const [archiveBusy, setArchiveBusy] = useState(false);

  const refresh = useCallback(async () => {
    const data = await getCategoryTree();
    setTree(data.tree || []);
  }, []);

  useEffect(() => {
    if (!user || forbidden) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setFetching(true);
      setError(null);
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

  function openCreate(parentId = "") {
    setCreateForm(emptyCreateForm(parentId));
    setCreateOpen(true);
  }

  function openArchive(id: string) {
    setArchiveId(id);
    setArchiveReassignTo("");
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    const name = createForm.name.trim();
    if (!name) {
      setError("Category name is required.");
      return;
    }
    setCreateBusy(true);
    setError(null);
    try {
      await createCategory({
        name,
        description: createForm.description.trim() || null,
        parent_id: createForm.parent_id || null,
        status: createForm.status || "ACTIVE",
      });
      setCreateOpen(false);
      setCreateForm(emptyCreateForm());
      await refresh();
      toast.push("Category created", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setCreateBusy(false);
    }
  }

  async function onArchive() {
    if (!archiveId) return;
    setArchiveBusy(true);
    setError(null);
    const target = findCategory(tree, archiveId);
    const productCount = target?.product_count ?? 0;
    try {
      await archiveCategory(
        archiveId,
        productCount > 0
          ? {
              reassign_products: true,
              reassign_to_category_id: archiveReassignTo || null,
            }
          : undefined,
      );
      setArchiveId(null);
      setArchiveReassignTo("");
      await refresh();
      toast.push("Category archived", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setArchiveBusy(false);
    }
  }

  const parentOptions = flattenForSelect(tree);
  const archiveTarget = archiveId ? findCategory(tree, archiveId) : null;
  const archiveProductCount = archiveTarget?.product_count ?? 0;
  const reassignOptions = archiveId
    ? flattenForSelect(tree, 0, archiveId)
    : [];

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
              href="/crm/products"
              className="inline-flex h-9 items-center justify-center gap-2 rounded-[var(--radius-md)] border border-border bg-surface px-3 text-sm font-semibold text-text-primary transition-[background-color,border-color] hover:border-teal/40 hover:bg-teal-soft"
            >
              <Package className="size-4" aria-hidden />
              Products
            </Link>
            {canCreate ? (
              <Button onClick={() => openCreate()}>
                <Plus className="size-4" aria-hidden />
                {copy.create}
              </Button>
            ) : null}
          </div>
        }
      />

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

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : tree.length === 0 ? (
        <EmptyState
          icon={<FolderTree className="size-8" />}
          title={copy.empty}
          description={copy.emptyHint}
        />
      ) : (
        <Surface className="p-4">
          <ul className="space-y-2">
            {tree.map((node) => (
              <CategoryNode
                key={node.id}
                node={node}
                depth={0}
                canCreate={canCreate}
                canDelete={canDelete}
                onAddChild={(parentId) => openCreate(parentId)}
                onArchive={(id) => openArchive(id)}
              />
            ))}
          </ul>
        </Surface>
      )}

      <DetailDrawer
        open={createOpen}
        onClose={() => {
          if (createBusy) return;
          setCreateOpen(false);
        }}
        title={
          createForm.parent_id ? copy.createChild : copy.create
        }
        description="Categories can be nested under a parent."
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
              required
            />
          </Field>
          <Field label="Parent">
            <Select
              value={createForm.parent_id}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, parent_id: e.target.value }))
              }
            >
              <option value="">Root (no parent)</option>
              {parentOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Field>
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

      <DetailDrawer
        open={Boolean(archiveId)}
        onClose={() => {
          if (archiveBusy) return;
          setArchiveId(null);
          setArchiveReassignTo("");
        }}
        title="Archive category?"
        description={
          archiveProductCount > 0
            ? `This category has ${archiveProductCount} active product${
                archiveProductCount === 1 ? "" : "s"
              }. Choose where to move them, or clear their category.`
            : "Archive this category. You can restore it later."
        }
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={archiveBusy}
              onClick={() => {
                setArchiveId(null);
                setArchiveReassignTo("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              disabled={archiveBusy}
              onClick={() => {
                void onArchive();
              }}
            >
              {archiveBusy ? "Archiving…" : "Archive"}
            </Button>
          </div>
        }
      >
        {archiveProductCount > 0 ? (
          <Field label="Reassign products to">
            <Select
              value={archiveReassignTo}
              onChange={(e) => setArchiveReassignTo(e.target.value)}
            >
              <option value="">Clear category (no category)</option>
              {reassignOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <p className="text-sm text-text-secondary">
            No active products are assigned to this category.
          </p>
        )}
      </DetailDrawer>
    </AppShell>
  );
}

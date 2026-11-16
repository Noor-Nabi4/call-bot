"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import {
  createServiceCategory,
  getServiceCategoryTree,
  type ServiceCategory,
} from "@/lib/api/services";
import { useAuth } from "@/lib/use-auth";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Select,
  Textarea,
} from "@/components/ui";

function CategoryNode({ node, depth = 0 }: { node: ServiceCategory; depth?: number }) {
  return (
    <li className="py-1">
      <div style={{ paddingLeft: depth * 16 }} className="flex items-center gap-2">
        <span className="font-medium">{node.name}</span>
        <span className="text-xs text-text-muted">
          {node.service_count ?? 0} services
        </span>
      </div>
      {node.children && node.children.length > 0 ? (
        <ul>
          {node.children.map((child) => (
            <CategoryNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function flatten(
  nodes: ServiceCategory[],
  depth = 0,
): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = [];
  for (const n of nodes) {
    out.push({ id: n.id, label: `${"— ".repeat(depth)}${n.name}` });
    if (n.children?.length) out.push(...flatten(n.children, depth + 1));
  }
  return out;
}

export default function ServiceCategoriesPage() {
  const { user, loading: authLoading } = useAuth();
  const [tree, setTree] = useState<ServiceCategory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    parent_id: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getServiceCategoryTree();
      setTree(res.tree);
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) void load();
  }, [authLoading, user, load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await createServiceCategory({
        name: form.name,
        description: form.description || null,
        parent_id: form.parent_id || null,
      });
      setForm({ name: "", description: "", parent_id: "" });
      await load();
    } catch (err) {
      setError(safeUserError(err));
    } finally {
      setCreating(false);
    }
  }

  const parents = flatten(tree);

  if (authLoading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Service categories"
        description="Nested categories for the service catalog."
        actions={
          <Link href="/crm/services">
            <Button variant="secondary">Services</Button>
          </Link>
        }
      />
      {error ? <ErrorState message={error} onRetry={() => void load()} /> : null}
      {loading ? (
        <LoadingSkeleton rows={6} />
      ) : tree.length === 0 ? (
        <EmptyState
          title="No categories"
          description="Create categories such as HVAC or Plumbing."
        />
      ) : (
        <ul className="rounded-lg border border-border bg-surface p-4">
          {tree.map((node) => (
            <CategoryNode key={node.id} node={node} />
          ))}
        </ul>
      )}

      <form onSubmit={onCreate} className="mt-8 grid max-w-xl gap-3">
        <h2 className="text-lg font-semibold">Create category</h2>
        <Field label="Name">
          <Input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field label="Parent">
          <Select
            value={form.parent_id}
            onChange={(e) => setForm({ ...form, parent_id: e.target.value })}
          >
            <option value="">Root</option>
            {parents.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Description">
          <Textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </Field>
        <Button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create category"}
        </Button>
      </form>
    </AppShell>
  );
}

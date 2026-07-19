"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Trash2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Field,
  FilterBar,
  Input,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  Surface,
  Textarea,
  useToast,
} from "@/components/ui";

const API_BASE =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

type Article = {
  id: string;
  title: string;
  body: string;
  category: string;
  tags: string[];
  is_active: boolean;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export default function KnowledgePage() {
  const { user, loading } = useAuth({ roles: ["admin", "dispatcher"] });
  const toast = useToast();
  const [articles, setArticles] = useState<Article[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "active" | "inactive">("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: "",
    body: "",
    category: "faq",
    tags: "",
  });

  const refresh = useCallback(async () => {
    const data = await api<{ articles: Article[] }>("/api/knowledge");
    setArticles(data.articles);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refresh()
        .catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, refresh]);

  const filtered = useMemo(() => {
    return articles.filter((a) => {
      if (statusFilter === "active" && !a.is_active) return false;
      if (statusFilter === "inactive" && a.is_active) return false;
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        a.title.toLowerCase().includes(q) ||
        a.body.toLowerCase().includes(q) ||
        a.category.toLowerCase().includes(q) ||
        a.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  }, [articles, search, statusFilter]);

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/knowledge", {
        method: "POST",
        body: JSON.stringify({
          title: form.title,
          body: form.body,
          category: form.category,
          tags: form.tags
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean),
        }),
      });
      setForm({ title: "", body: "", category: "faq", tags: "" });
      setShowForm(false);
      await refresh();
      toast.push("Article created", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  async function onConfirmDelete() {
    if (!deleteId) return;
    setDeleteBusy(true);
    setError(null);
    try {
      await api(`/api/knowledge/${deleteId}`, { method: "DELETE" });
      setDeleteId(null);
      await refresh();
      toast.push("Article deleted", "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title="Knowledge base"
        description="Curated FAQs and policies the voice agent can retrieve."
        actions={
          <Button size="sm" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Hide form" : "New article"}
          </Button>
        }
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => setError(null)} />
      ) : null}

      {showForm ? (
        <Surface className="mb-4 p-4">
          <form onSubmit={onCreate} className="grid gap-3">
            <Field label="Title">
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </Field>
            <Field label="Body">
              <Textarea
                rows={4}
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                required
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Category">
                <Input
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                />
              </Field>
              <Field label="Tags" hint="Comma-separated">
                <Input
                  value={form.tags}
                  onChange={(e) => setForm({ ...form, tags: e.target.value })}
                />
              </Field>
            </div>
            <Button type="submit" className="w-fit">
              Add article
            </Button>
          </form>
        </Surface>
      ) : null}

      <FilterBar>
        <SearchInput
          className="min-w-[12rem] flex-1"
          placeholder="Search articles…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch("")}
        />
        <Select
          className="w-auto min-w-[8rem]"
          value={statusFilter}
          onChange={(e) =>
            setStatusFilter(e.target.value as "" | "active" | "inactive")
          }
          aria-label="Filter by status"
        >
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </Select>
      </FilterBar>

      {fetching ? (
        <LoadingSkeleton rows={4} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="size-8" />}
          title={search || statusFilter ? "No matching articles" : "No articles yet"}
          description="Create articles for the voice agent to retrieve during calls."
          action={
            !showForm ? (
              <Button size="sm" onClick={() => setShowForm(true)}>
                New article
              </Button>
            ) : undefined
          }
        />
      ) : (
        <ul className="space-y-3">
          {filtered.map((a) => (
            <li key={a.id}>
              <Surface className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-text-primary">{a.title}</h3>
                      <StatusPill status={a.is_active ? "active" : "inactive"} />
                    </div>
                    <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-text-muted">
                      {a.category}
                    </p>
                    {a.tags.length > 0 ? (
                      <p className="mt-1 text-xs text-text-secondary">
                        {a.tags.join(", ")}
                      </p>
                    ) : null}
                    <p className="mt-2 whitespace-pre-wrap text-sm text-text-secondary">
                      {a.body}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="shrink-0 text-danger hover:text-danger"
                    onClick={() => setDeleteId(a.id)}
                    aria-label={`Delete ${a.title}`}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </Surface>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={!!deleteId}
        title="Delete article?"
        description="This removes the article from the knowledge base. The voice agent will no longer retrieve it."
        confirmLabel="Delete"
        danger
        busy={deleteBusy}
        onConfirm={onConfirmDelete}
        onCancel={() => setDeleteId(null)}
      />
    </AppShell>
  );
}

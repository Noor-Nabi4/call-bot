"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { BookOpen, Pencil, Search, Trash2 } from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { errors, knowledge as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import { listAgentProfiles } from "@/lib/api/agents";
import type { AgentProfile } from "@/types";
import {
  Button,
  ConfirmDialog,
  DetailDrawer,
  EmptyState,
  ErrorState,
  ForbiddenState,
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

const ARTICLE_FORM_ID = "knowledge-article-form";

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
  agent_profile_id: string | null;
};

type SearchHit = Article & { score?: number };

type ArticleForm = {
  title: string;
  body: string;
  category: string;
  tags: string;
  agent_profile_id: string;
  is_active: boolean;
};

const emptyForm = (): ArticleForm => ({
  title: "",
  body: "",
  category: "faq",
  tags: "",
  agent_profile_id: "",
  is_active: true,
});

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let message: string = errors.generic;
    try {
      const body = (await res.json()) as {
        detail?: { message?: string } | string;
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      /* keep generic */
    }
    throw new Error(message);
  }
  return res.json();
}

export default function KnowledgePage() {
  const { user, loading, forbidden } = useAuth({ permission: "knowledge.read" });
  const toast = useToast();
  const [articles, setArticles] = useState<Article[]>([]);
  const [profiles, setProfiles] = useState<AgentProfile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"" | "active" | "inactive">(
    "",
  );
  const [categoryFilter, setCategoryFilter] = useState("");
  const [profileFilter, setProfileFilter] = useState("");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ArticleForm>(emptyForm);
  const [saveBusy, setSaveBusy] = useState(false);
  const [previewQuery, setPreviewQuery] = useState("");
  const [previewHits, setPreviewHits] = useState<SearchHit[] | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewProfileId, setPreviewProfileId] = useState("");

  const refresh = useCallback(async () => {
    const [data, profileData] = await Promise.all([
      api<{ articles: Article[] }>("/api/knowledge"),
      listAgentProfiles(),
    ]);
    setArticles(data.articles);
    setProfiles(profileData.profiles || []);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      refresh()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, refresh]);

  const categories = useMemo(() => {
    const set = new Set(articles.map((a) => a.category).filter(Boolean));
    return Array.from(set).sort();
  }, [articles]);

  const profileName = useCallback(
    (id: string | null) => {
      if (!id) return copy.allAgents;
      return profiles.find((p) => p.id === id)?.name || id.slice(0, 8);
    },
    [profiles],
  );

  const filtered = useMemo(() => {
    return articles.filter((a) => {
      if (statusFilter === "active" && !a.is_active) return false;
      if (statusFilter === "inactive" && a.is_active) return false;
      if (categoryFilter && a.category !== categoryFilter) return false;
      if (profileFilter === "shared" && a.agent_profile_id) return false;
      if (
        profileFilter &&
        profileFilter !== "shared" &&
        a.agent_profile_id !== profileFilter
      ) {
        return false;
      }
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        a.title.toLowerCase().includes(q) ||
        a.body.toLowerCase().includes(q) ||
        a.category.toLowerCase().includes(q) ||
        a.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  }, [articles, search, statusFilter, categoryFilter, profileFilter]);

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

  function closeForm() {
    if (saveBusy) return;
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm());
  }

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm());
    setShowForm(true);
  }

  function openEdit(article: Article) {
    setEditingId(article.id);
    setForm({
      title: article.title,
      body: article.body,
      category: article.category,
      tags: article.tags.join(", "),
      agent_profile_id: article.agent_profile_id || "",
      is_active: article.is_active,
    });
    setShowForm(true);
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaveBusy(true);
    setError(null);
    const payload = {
      title: form.title,
      body: form.body,
      category: form.category,
      tags: form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      agent_profile_id: form.agent_profile_id || null,
      is_active: form.is_active,
    };
    try {
      if (editingId) {
        await api(`/api/knowledge/${editingId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.push(copy.updated, "success");
      } else {
        await api("/api/knowledge", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.push(copy.created, "success");
      }
      setForm(emptyForm());
      setEditingId(null);
      setShowForm(false);
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setSaveBusy(false);
    }
  }

  async function onToggleActive(article: Article) {
    setError(null);
    try {
      await api(`/api/knowledge/${article.id}`, {
        method: "PUT",
        body: JSON.stringify({
          title: article.title,
          body: article.body,
          category: article.category,
          tags: article.tags,
          agent_profile_id: article.agent_profile_id,
          is_active: !article.is_active,
        }),
      });
      toast.push(
        article.is_active ? copy.deactivated : copy.reactivated,
        "success",
      );
      await refresh();
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
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
      toast.push(copy.deleted, "success");
    } catch (err) {
      setError(safeUserError(err, errors.deleteFailed));
    } finally {
      setDeleteBusy(false);
    }
  }

  async function onPreviewSearch(e: FormEvent) {
    e.preventDefault();
    if (!previewQuery.trim()) return;
    setPreviewBusy(true);
    setError(null);
    try {
      const data = await api<{ articles: SearchHit[] }>("/api/knowledge/search", {
        method: "POST",
        body: JSON.stringify({
          query: previewQuery.trim(),
          limit: 5,
          agent_profile_id: previewProfileId || null,
        }),
      });
      setPreviewHits(data.articles || []);
    } catch (err) {
      setError(safeUserError(err, copy.previewFailed));
      setPreviewHits(null);
    } finally {
      setPreviewBusy(false);
    }
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <Button size="sm" onClick={openCreate}>
            {copy.add}
          </Button>
        }
      />

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => setError(null)} />
      ) : null}

      <Surface className="mb-4 p-4">
        <div className="flex items-center gap-2">
          <Search className="size-4 text-text-muted" aria-hidden />
          <h2 className="m-0 text-sm font-semibold text-ink">{copy.preview}</h2>
        </div>
        <p className="mt-1 m-0 text-sm text-text-secondary">{copy.previewHint}</p>
        <form onSubmit={onPreviewSearch} className="mt-3 flex flex-wrap gap-2">
          <Input
            className="min-w-[12rem] flex-1"
            placeholder={copy.previewPlaceholder}
            value={previewQuery}
            onChange={(e) => setPreviewQuery(e.target.value)}
          />
          <Select
            className="w-auto min-w-[10rem]"
            value={previewProfileId}
            onChange={(e) => setPreviewProfileId(e.target.value)}
            aria-label={copy.agentScope}
          >
            <option value="">{copy.allAgents}</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
          <Button type="submit" disabled={previewBusy || !previewQuery.trim()}>
            {previewBusy ? copy.previewing : copy.runPreview}
          </Button>
        </form>
        {previewHits ? (
          <ul className="mt-3 m-0 list-none space-y-2 p-0">
            {previewHits.length === 0 ? (
              <li className="text-sm text-text-secondary">{copy.previewEmpty}</li>
            ) : (
              previewHits.map((h) => (
                <li
                  key={h.id}
                  className="rounded-[10px] border border-border bg-surface-2 px-3 py-2"
                >
                  <p className="m-0 text-sm font-medium text-ink">
                    {h.title}
                    {h.score != null ? (
                      <span className="ml-2 font-mono text-xs text-text-muted">
                        score {h.score}
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-1 m-0 line-clamp-2 text-xs text-text-secondary">
                    {h.body}
                  </p>
                </li>
              ))
            )}
          </ul>
        ) : null}
      </Surface>

      <FilterBar>
        <SearchInput
          className="min-w-[12rem] flex-1"
          placeholder="Filter articles…"
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
          <option value="">All statuses</option>
          <option value="active">{copy.ready}</option>
          <option value="inactive">{copy.needsAttention}</option>
        </Select>
        <Select
          className="w-auto min-w-[8rem]"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
        <Select
          className="w-auto min-w-[10rem]"
          value={profileFilter}
          onChange={(e) => setProfileFilter(e.target.value)}
          aria-label="Filter by agent"
        >
          <option value="">All scopes</option>
          <option value="shared">{copy.allAgents}</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
      </FilterBar>

      {fetching ? (
        <LoadingSkeleton rows={4} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="size-8" />}
          title={
            search || statusFilter || categoryFilter || profileFilter
              ? "No matching articles"
              : copy.empty
          }
          description={copy.emptyHint}
          action={
            <Button size="sm" onClick={openCreate}>
              {copy.add}
            </Button>
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
                      <StatusPill
                        status={a.is_active ? "ready" : "needs_attention"}
                      />
                    </div>
                    <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-text-muted">
                      {a.category} · {profileName(a.agent_profile_id)}
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
                  <div className="flex shrink-0 flex-col gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEdit(a)}
                      aria-label={`Edit ${a.title}`}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onToggleActive(a)}
                    >
                      {a.is_active ? copy.deactivate : copy.reactivate}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-danger hover:text-danger"
                      onClick={() => setDeleteId(a.id)}
                      aria-label={`Delete ${a.title}`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              </Surface>
            </li>
          ))}
        </ul>
      )}

      <DetailDrawer
        open={showForm}
        onClose={closeForm}
        title={editingId ? copy.edit : copy.add}
        description={copy.agentScopeHint}
        width="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={closeForm} disabled={saveBusy}>
              Cancel
            </Button>
            <Button
              form={ARTICLE_FORM_ID}
              type="submit"
              disabled={saveBusy}
            >
              {saveBusy ? copy.saving : editingId ? copy.save : copy.add}
            </Button>
          </div>
        }
      >
        <form id={ARTICLE_FORM_ID} onSubmit={onSave} className="grid gap-3">
          <Field label="Title">
            <Input
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              required
            />
          </Field>
          <Field label="Body">
            <Textarea
              rows={6}
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
              required
            />
          </Field>
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
          <Field label={copy.agentScope} hint={copy.agentScopeHint}>
            <Select
              value={form.agent_profile_id}
              onChange={(e) =>
                setForm({ ...form, agent_profile_id: e.target.value })
              }
            >
              <option value="">{copy.allAgents}</option>
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          </Field>
          {editingId ? (
            <Field label="Status">
              <Select
                value={form.is_active ? "active" : "inactive"}
                onChange={(e) =>
                  setForm({
                    ...form,
                    is_active: e.target.value === "active",
                  })
                }
              >
                <option value="active">{copy.ready}</option>
                <option value="inactive">{copy.needsAttention}</option>
              </Select>
            </Field>
          ) : null}
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={!!deleteId}
        title={copy.deleteTitle}
        description={copy.deleteBody}
        confirmLabel="Delete"
        danger
        busy={deleteBusy}
        onConfirm={onConfirmDelete}
        onCancel={() => setDeleteId(null)}
      />
    </AppShell>
  );
}

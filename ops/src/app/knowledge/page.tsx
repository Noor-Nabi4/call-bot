"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";

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
  const [articles, setArticles] = useState<Article[]>([]);
  const [error, setError] = useState<string | null>(null);
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
    refresh().catch((e) => setError(e.message));
  }, [user, refresh]);

  if (loading || !user) return <p className="p-6 text-ink-muted">Loading…</p>;

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
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  async function onDelete(id: string) {
    await api(`/api/knowledge/${id}`, { method: "DELETE" });
    await refresh();
  }

  return (
    <AppShell user={user}>
      <h2 className="text-xl font-semibold">Knowledge base</h2>
      <p className="text-sm text-ink-muted">
        Curated FAQs and policies the voice agent can retrieve.
      </p>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}

      <form
        onSubmit={onCreate}
        className="mt-4 grid gap-2 rounded border border-line bg-panel p-4"
      >
        <input
          className="rounded border border-line px-2 py-1.5 text-sm"
          placeholder="Title"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          required
        />
        <textarea
          className="rounded border border-line px-2 py-1.5 text-sm"
          placeholder="Body"
          rows={3}
          value={form.body}
          onChange={(e) => setForm({ ...form, body: e.target.value })}
          required
        />
        <div className="grid gap-2 md:grid-cols-3">
          <input
            className="rounded border border-line px-2 py-1.5 text-sm"
            placeholder="Category"
            value={form.category}
            onChange={(e) => setForm({ ...form, category: e.target.value })}
          />
          <input
            className="rounded border border-line px-2 py-1.5 text-sm md:col-span-2"
            placeholder="Tags (comma-separated)"
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
          />
        </div>
        <button
          type="submit"
          className="w-fit rounded bg-accent px-3 py-1.5 text-sm text-white"
        >
          Add article
        </button>
      </form>

      <ul className="mt-6 space-y-3">
        {articles.map((a) => (
          <li
            key={a.id}
            className="rounded border border-line bg-panel p-3 text-sm"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-semibold">{a.title}</p>
                <p className="text-xs uppercase text-ink-muted">{a.category}</p>
                <p className="mt-1 whitespace-pre-wrap text-ink-muted">{a.body}</p>
              </div>
              <button
                type="button"
                className="text-danger text-xs"
                onClick={() => onDelete(a.id)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </AppShell>
  );
}

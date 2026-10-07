const API_BASE =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type KnowledgeSource = {
  id: string;
  source_type: string;
  name: string;
  description: string | null;
  status: string;
  version: number;
  active_version: number | null;
  chunk_count: number;
  failure_code: string | null;
  failure_message: string | null;
  last_indexed_at: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown>;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let message = "Request failed";
    try {
      const body = (await res.json()) as {
        detail?: { message?: string } | string;
      };
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export function listKnowledgeSources(): Promise<{ sources: KnowledgeSource[] }> {
  return api("/api/knowledge/sources");
}

export function createTextSource(body: {
  name: string;
  text: string;
  sourceType?: string;
  metadata?: Record<string, unknown>;
  sync?: boolean;
}): Promise<{ source: KnowledgeSource }> {
  return api("/api/knowledge/sources/text", {
    method: "POST",
    body: JSON.stringify({
      name: body.name,
      text: body.text,
      sourceType: body.sourceType || "TEXT",
      metadata: body.metadata || {},
      sync: body.sync ?? true,
    }),
  });
}

export function createWebsiteSource(body: {
  name: string;
  url: string;
  sync?: boolean;
}): Promise<{ source: KnowledgeSource }> {
  return api("/api/knowledge/sources/website", {
    method: "POST",
    body: JSON.stringify({
      name: body.name,
      url: body.url,
      sync: body.sync ?? false,
    }),
  });
}

export function reindexSource(
  id: string,
  sync = true
): Promise<{ source: KnowledgeSource }> {
  return api(`/api/knowledge/sources/${id}/reindex?sync=${sync ? "true" : "false"}`, {
    method: "POST",
  });
}

export function deleteSource(id: string): Promise<{ ok: boolean }> {
  return api(`/api/knowledge/sources/${id}`, { method: "DELETE" });
}

export function semanticSearch(query: string): Promise<{
  status: string;
  results: Array<{
    source_title: string;
    content: string;
    score: number;
    source_type: string;
  }>;
  count: number;
}> {
  return api("/api/knowledge/semantic-search", {
    method: "POST",
    body: JSON.stringify({ query, topK: 5 }),
  });
}

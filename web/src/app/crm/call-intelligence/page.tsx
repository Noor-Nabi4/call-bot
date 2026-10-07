"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { searchCallIntelligence } from "@/lib/api/call-intelligence";
import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  ForbiddenState,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
} from "@/components/ui";

type Hit = {
  call_id: string;
  snippet: string;
  classification: string | null;
  sentiment: string | null;
  intent: string | null;
};

export default function CallIntelligenceSearchPage() {
  const { user, loading, forbidden } = useAuth({
    permission: "calls.transcripts.read",
  });
  const [q, setQ] = useState("");
  const [classification, setClassification] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [items, setItems] = useState<Hit[]>([]);
  const [total, setTotal] = useState(0);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async () => {
    setFetching(true);
    setError(null);
    try {
      const res = await searchCallIntelligence({
        q: q.trim() || undefined,
        classification: classification || undefined,
        sentiment: sentiment || undefined,
        limit: 50,
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      setFetching(false);
    }
  }, [q, classification, sentiment]);

  useEffect(() => {
    if (!user) return;
    void runSearch();
  }, [user, runSearch]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void runSearch();
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

  return (
    <AppShell user={user}>
      <PageHeader
        title="Call Intelligence"
        description="Search transcripts and AI classifications across calls."
      />
      <form
        onSubmit={onSubmit}
        className="mb-6 flex flex-wrap items-end gap-3"
      >
        <Field label="Search">
          <SearchInput
            className="w-full sm:w-72"
            placeholder="Phrase or keyword…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onClear={() => setQ("")}
          />
        </Field>
        <Field label="Classification">
          <Select
            value={classification}
            onChange={(e) => setClassification(e.target.value)}
          >
            <option value="">Any</option>
            {[
              "BOOKING",
              "SALES",
              "SUPPORT",
              "BILLING",
              "SPAM",
              "HUMAN_TRANSFER",
              "OTHER",
            ].map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, " ")}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Sentiment">
          <Select
            value={sentiment}
            onChange={(e) => setSentiment(e.target.value)}
          >
            <option value="">Any</option>
            {["POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED", "UNKNOWN"].map(
              (s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ),
            )}
          </Select>
        </Field>
        <Button type="submit" size="sm" disabled={fetching}>
          Search
        </Button>
      </form>

      {error ? (
        <ErrorState className="mb-4" message={error} onRetry={() => void runSearch()} />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={4} />
      ) : items.length === 0 ? (
        <EmptyState
          title="No matching transcripts"
          description="Try a different phrase or clear filters."
        />
      ) : (
        <ul className="space-y-3">
          <li className="text-xs text-text-muted">{total} result(s)</li>
          {items.map((hit) => (
            <li
              key={hit.call_id}
              className="rounded-lg border border-border px-4 py-3"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                <Link
                  href={`/calls?highlight=${hit.call_id}`}
                  className="font-medium text-brand hover:underline"
                >
                  Call {hit.call_id.slice(0, 8)}…
                </Link>
                {hit.classification ? (
                  <span>{hit.classification.replace(/_/g, " ")}</span>
                ) : null}
                {hit.sentiment ? <span>· {hit.sentiment}</span> : null}
                {hit.intent ? <span>· {hit.intent}</span> : null}
              </div>
              <p className="mt-2 text-sm text-text-primary">{hit.snippet}</p>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}

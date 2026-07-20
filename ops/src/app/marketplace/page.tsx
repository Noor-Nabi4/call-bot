"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Store } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  getMarketplaceCatalog,
  installMarketplaceAgent,
} from "@/lib/api";
import { useAuth } from "@/lib/use-auth";
import { errors, marketplace as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";
import type { IndustryTemplate } from "@/types";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  FilterBar,
  LoadingSkeleton,
  PageHeader,
  Select,
  Surface,
  useToast,
} from "@/components/ui";

export default function MarketplacePage() {
  const { user, loading } = useAuth({ roles: ["admin"] });
  const toast = useToast();
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [category, setCategory] = useState("all");
  const [seedKnowledge, setSeedKnowledge] = useState(true);
  const [setDefault, setSetDefault] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [installingKey, setInstallingKey] = useState<string | null>(null);
  const [installTarget, setInstallTarget] = useState<IndustryTemplate | null>(
    null,
  );

  const load = useCallback(async () => {
    const data = await getMarketplaceCatalog();
    setTemplates(data.templates || []);
    setCategories(data.categories || []);
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      load()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, load]);

  const visible = useMemo(() => {
    if (category === "all") return templates;
    return templates.filter((t) => t.category === category);
  }, [templates, category]);

  async function onConfirmInstall() {
    if (!installTarget) return;
    setInstallingKey(installTarget.key);
    try {
      const data = await installMarketplaceAgent({
        industry_key: installTarget.key,
        seed_knowledge: seedKnowledge,
        set_as_default: setDefault,
      });
      toast.push(copy.installed, "success");
      setInstallTarget(null);
      window.location.assign(`/agents/${data.profile.id}`);
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    } finally {
      setInstallingKey(null);
    }
  }

  if (loading || !user) {
    return (
      <div className="p-6">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <AppShell user={user}>
      <PageHeader
        title={copy.title}
        description={copy.description}
        actions={
          <FilterBar className="mb-0 border-0 bg-transparent p-0">
            <Select
              className="w-auto"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-label="Category"
            >
              <option value="all">{copy.all}</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </FilterBar>
        }
      />

      <div className="mb-4 flex flex-wrap gap-4 text-sm text-text-secondary">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={seedKnowledge}
            onChange={(e) => setSeedKnowledge(e.target.checked)}
          />
          {copy.seedKnowledge}
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={setDefault}
            onChange={(e) => setSetDefault(e.target.checked)}
          />
          {copy.setDefault}
        </label>
        <Link href="/agents" className="font-medium text-brand hover:underline">
          {copy.openAgent}
        </Link>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : null}

      {fetching ? <LoadingSkeleton rows={5} /> : null}

      {!fetching && !error && visible.length === 0 ? (
        <EmptyState
          icon={<Store className="size-8" />}
          title={copy.empty}
        />
      ) : null}

      {!fetching && !error && visible.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((template) => {
            const busy = installingKey === template.key;
            return (
              <Surface key={template.key} className="flex flex-col p-4">
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-medium tracking-wide text-text-muted uppercase">
                      {template.category || "General"}
                      {template.featured ? ` · ${copy.featured}` : ""}
                    </p>
                    <h2 className="mt-1 font-heading text-lg font-semibold text-text-primary">
                      {template.name}
                    </h2>
                  </div>
                  <span className="rounded-md bg-surface-muted px-2 py-0.5 font-mono text-[11px] text-text-secondary">
                    {template.agent_type}
                  </span>
                </div>
                <p className="mb-3 flex-1 text-sm text-text-secondary">
                  {template.marketplace_blurb || template.description}
                </p>
                <p className="mb-3 text-xs text-text-muted">
                  {template.suggested_article_count} {copy.articles}
                </p>
                {template.example_questions?.length ? (
                  <ul className="mb-4 space-y-1 text-xs text-text-secondary">
                    {template.example_questions.slice(0, 3).map((q) => (
                      <li key={q}>“{q}”</li>
                    ))}
                  </ul>
                ) : null}
                <Button
                  size="sm"
                  disabled={busy || installingKey != null}
                  onClick={() => setInstallTarget(template)}
                >
                  {busy ? copy.installing : copy.install}
                </Button>
              </Surface>
            );
          })}
        </div>
      ) : null}

      <ConfirmDialog
        open={!!installTarget}
        title={copy.installTitle}
        description={
          installTarget
            ? copy.installBody.replace("{name}", installTarget.name)
            : undefined
        }
        confirmLabel={copy.install}
        busy={installingKey != null}
        onConfirm={() => {
          void onConfirmInstall();
        }}
        onCancel={() => {
          if (installingKey) return;
          setInstallTarget(null);
        }}
      />
    </AppShell>
  );
}

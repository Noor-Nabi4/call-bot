"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Blocks,
  Calculator,
  CalendarDays,
  CircleAlert,
  CircleCheck,
  KeyRound,
  RefreshCw,
  ShoppingCart,
  Unplug,
  UsersRound,
} from "lucide-react";
import { AppShell } from "@/components/shell";
import { useAuth } from "@/lib/use-auth";
import { hasPermission } from "@/lib/permissions";
import { errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  connectApiKey,
  disconnectIntegration,
  getIntegration,
  listIntegrationProviders,
  listIntegrations,
  startConnect,
  statusLabel,
  syncIntegration,
  type IntegrationConnection,
  type IntegrationCategory,
  type ProviderDescriptor,
} from "@/lib/api/integrations";
import {
  Button,
  ConfirmDialog,
  DetailDrawer,
  EmptyState,
  ErrorState,
  ForbiddenState,
  Field,
  Input,
  LoadingSkeleton,
  PageHeader,
  Surface,
  useToast,
} from "@/components/ui";

const CATEGORIES: {
  key: IntegrationCategory;
  label: string;
  icon: typeof Blocks;
}[] = [
  { key: "crm", label: "CRM", icon: UsersRound },
  { key: "calendar", label: "Calendar", icon: CalendarDays },
  { key: "commerce", label: "Commerce", icon: ShoppingCart },
  { key: "accounting", label: "Accounting", icon: Calculator },
];

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "Never";
  const seconds = Math.round((Date.now() - t) / 1000);
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
  return new Date(t).toLocaleString();
}

function StatusBadge({ status }: { status: string }) {
  const healthy = status === "CONNECTED" || status === "SYNCED";
  const warn = status === "REAUTH_REQUIRED" || status === "ERROR";
  const Icon = healthy ? CircleCheck : warn ? CircleAlert : RefreshCw;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-sm ${
        healthy
          ? "text-emerald-700"
          : warn
            ? "text-amber-700"
            : "text-text-muted"
      }`}
    >
      <Icon className="size-3.5" aria-hidden />
      {statusLabel(status)}
    </span>
  );
}

export default function IntegrationsPage() {
  const { user, loading, forbidden } = useAuth({
    permission: "integrations.read",
  });
  const toast = useToast();
  const canConnect = hasPermission(user, "integrations.connect");
  const canSync = hasPermission(user, "integrations.sync");
  const canDelete = hasPermission(user, "integrations.delete");

  const [providers, setProviders] = useState<ProviderDescriptor[]>([]);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<IntegrationConnection | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [disconnectTarget, setDisconnectTarget] =
    useState<IntegrationConnection | null>(null);
  const [apiKeyProvider, setApiKeyProvider] = useState<string | null>(null);
  const [wooStore, setWooStore] = useState("");
  const [wooKey, setWooKey] = useState("");
  const [wooSecret, setWooSecret] = useState("");
  const [wooBusy, setWooBusy] = useState(false);
  const [shopifyShop, setShopifyShop] = useState("");
  const [shopifyOpen, setShopifyOpen] = useState(false);

  const byProvider = useMemo(() => {
    const map = new Map<string, IntegrationConnection>();
    for (const c of connections) map.set(c.provider, c);
    return map;
  }, [connections]);

  const load = useCallback(async () => {
    const [p, c] = await Promise.all([
      listIntegrationProviders(),
      listIntegrations(),
    ]);
    setProviders(p.providers || []);
    setConnections(c.integrations || []);
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

  async function onConnect(provider: ProviderDescriptor) {
    if (!canConnect) return;
    if (!provider.platform_configured && provider.oauth) {
      toast.push("Not configured on this platform", "error");
      return;
    }
    if (!provider.oauth) {
      setApiKeyProvider(provider.key);
      return;
    }
    if (provider.key === "shopify") {
      setShopifyOpen(true);
      return;
    }
    try {
      const redirectUri = `${window.location.origin}/settings/integrations/callback?provider=${provider.key}`;
      const res = await startConnect(provider.key, redirectUri);
      window.location.assign(res.authorization_url);
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    }
  }

  async function onOpenDetail(conn: IntegrationConnection) {
    setDetailBusy(true);
    try {
      const res = await getIntegration(conn.id);
      setSelected(res.integration);
    } catch (e) {
      toast.push(safeUserError(e, errors.loadFailed), "error");
    } finally {
      setDetailBusy(false);
    }
  }

  async function onSync(conn: IntegrationConnection) {
    if (!canSync) return;
    try {
      await syncIntegration(conn.id);
      toast.push("Sync queued", "success");
      await load();
      if (selected?.id === conn.id) {
        const res = await getIntegration(conn.id);
        setSelected(res.integration);
      }
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    }
  }

  async function onConfirmDisconnect() {
    if (!disconnectTarget || !canDelete) return;
    try {
      await disconnectIntegration(disconnectTarget.id);
      toast.push("Integration disconnected", "success");
      setDisconnectTarget(null);
      setSelected(null);
      await load();
    } catch (e) {
      toast.push(safeUserError(e, errors.saveFailed), "error");
    }
  }

  async function onApiKeyConnect(e: FormEvent) {
    e.preventDefault();
    if (!apiKeyProvider) return;
    setWooBusy(true);
    try {
      if (apiKeyProvider === "woocommerce") {
        await connectApiKey("woocommerce", {
          store_url: wooStore.trim(),
          consumer_key: wooKey.trim(),
          consumer_secret: wooSecret.trim(),
          api_key: wooKey.trim(),
        });
      } else if (apiKeyProvider === "servicetitan") {
        await connectApiKey("servicetitan", {
          client_id: wooKey.trim(),
          client_secret: wooSecret.trim(),
          tenant_st_id: wooStore.trim(),
          api_key: wooKey.trim(),
        });
      } else {
        throw new Error("Unsupported API-key provider");
      }
      toast.push("Integration connected", "success");
      setApiKeyProvider(null);
      setWooStore("");
      setWooKey("");
      setWooSecret("");
      await load();
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
    } finally {
      setWooBusy(false);
    }
  }

  async function onShopifyConnect(e: FormEvent) {
    e.preventDefault();
    setWooBusy(true);
    try {
      const redirectUri = `${window.location.origin}/settings/integrations/callback?provider=shopify`;
      const res = await startConnect("shopify", redirectUri, shopifyShop.trim());
      window.location.assign(res.authorization_url);
    } catch (err) {
      toast.push(safeUserError(err, errors.saveFailed), "error");
      setWooBusy(false);
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

  return (
    <AppShell user={user}>
      <PageHeader
        title="Integrations"
        description="Connect external CRM, calendar, commerce, and accounting systems."
      />

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => void load()}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={6} />
      ) : providers.length === 0 ? (
        <EmptyState
          icon={<Blocks className="size-8" />}
          title="No providers"
          description="No integration providers are registered."
        />
      ) : (
        <div className="space-y-10">
          {CATEGORIES.map((cat) => {
            const items = providers.filter((p) => p.category === cat.key);
            if (items.length === 0) return null;
            const CatIcon = cat.icon;
            return (
              <section key={cat.key} aria-labelledby={`cat-${cat.key}`}>
                <div className="mb-3 flex items-center gap-2">
                  <CatIcon className="size-4 text-text-muted" aria-hidden />
                  <h2
                    id={`cat-${cat.key}`}
                    className="text-xs font-semibold uppercase tracking-[0.12em] text-text-muted"
                  >
                    {cat.label}
                  </h2>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {items.map((provider) => {
                    const conn = byProvider.get(provider.key);
                    const status = conn?.status || "DISCONNECTED";
                    const configured = provider.platform_configured;
                    return (
                      <Surface
                        key={provider.key}
                        className="flex flex-col gap-3 p-4"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h3 className="text-sm font-semibold">
                              {provider.name}
                            </h3>
                            <p className="mt-1 text-sm text-text-secondary">
                              {provider.description}
                            </p>
                          </div>
                          {!configured && provider.oauth ? (
                            <span className="shrink-0 text-xs text-text-muted">
                              Not configured
                            </span>
                          ) : (
                            <StatusBadge status={status} />
                          )}
                        </div>
                        <p className="text-xs text-text-muted">
                          Last sync: {relativeTime(conn?.last_sync_at ?? null)}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {provider.capabilities.slice(0, 4).map((cap) => (
                            <span
                              key={cap}
                              className="rounded bg-surface-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-muted"
                            >
                              {cap.replaceAll("_", " ")}
                            </span>
                          ))}
                        </div>
                        <div className="mt-auto flex flex-wrap gap-2">
                          {conn &&
                          status !== "DISCONNECTED" &&
                          status !== "DISABLED" ? (
                            <>
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => void onOpenDetail(conn)}
                                disabled={detailBusy}
                              >
                                Details
                              </Button>
                              {canSync ? (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => void onSync(conn)}
                                >
                                  <RefreshCw className="size-3.5" aria-hidden />
                                  Sync now
                                </Button>
                              ) : null}
                              {canConnect ? (
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => void onConnect(provider)}
                                  disabled={!configured && provider.oauth}
                                >
                                  <KeyRound className="size-3.5" aria-hidden />
                                  Reconnect
                                </Button>
                              ) : null}
                              {canDelete ? (
                                <Button
                                  size="sm"
                                  variant="danger"
                                  onClick={() => setDisconnectTarget(conn)}
                                >
                                  <Unplug className="size-3.5" aria-hidden />
                                  Disconnect
                                </Button>
                              ) : null}
                            </>
                          ) : canConnect ? (
                            <Button
                              size="sm"
                              onClick={() => void onConnect(provider)}
                              disabled={!configured && provider.oauth}
                            >
                              Connect
                            </Button>
                          ) : null}
                        </div>
                      </Surface>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}

      <DetailDrawer
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={selected?.provider_name || "Integration"}
      >
        {selected ? (
          <div className="space-y-6">
            <section>
              <h3 className="text-sm font-semibold">Connection</h3>
              <dl className="mt-2 space-y-1 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-text-muted">Status</dt>
                  <dd>
                    <StatusBadge status={selected.status} />
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-text-muted">Account</dt>
                  <dd>{selected.external_account_id || "—"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-text-muted">Connected</dt>
                  <dd>{relativeTime(selected.connected_at)}</dd>
                </div>
                {selected.health ? (
                  <div className="flex justify-between gap-4">
                    <dt className="text-text-muted">Health</dt>
                    <dd>{selected.health.status}</dd>
                  </div>
                ) : null}
              </dl>
            </section>
            <section>
              <h3 className="text-sm font-semibold">Sync</h3>
              <dl className="mt-2 space-y-1 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-text-muted">Last success</dt>
                  <dd>{relativeTime(selected.last_success_at)}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-text-muted">Direction</dt>
                  <dd>{selected.sync_direction}</dd>
                </div>
                {selected.last_error_message ? (
                  <p className="text-sm text-amber-800">
                    {selected.last_error_message}
                  </p>
                ) : null}
              </dl>
              {selected.recent_sync_runs?.length ? (
                <ul className="mt-3 space-y-2 text-sm">
                  {selected.recent_sync_runs.map((run) => (
                    <li
                      key={run.id}
                      className="flex justify-between gap-2 border-b border-border py-1"
                    >
                      <span>{run.status}</span>
                      <span className="text-text-muted">
                        {run.records_processed} processed
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
            <section>
              <h3 className="text-sm font-semibold">Capabilities</h3>
              <div className="mt-2 flex flex-wrap gap-1">
                {selected.capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="rounded bg-surface-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-muted"
                  >
                    {cap.replaceAll("_", " ")}
                  </span>
                ))}
              </div>
            </section>
            <div className="flex flex-wrap gap-2">
              {canSync ? (
                <Button size="sm" onClick={() => void onSync(selected)}>
                  Sync now
                </Button>
              ) : null}
              {canDelete ? (
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => setDisconnectTarget(selected)}
                >
                  Disconnect
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-text-muted">Loading…</p>
        )}
      </DetailDrawer>

      <ConfirmDialog
        open={Boolean(disconnectTarget)}
        title="Disconnect integration?"
        description="Credentials will be removed. Mappings are retained for re-link. This cannot be undone without reconnecting."
        confirmLabel="Disconnect"
        danger
        onConfirm={() => void onConfirmDisconnect()}
        onCancel={() => setDisconnectTarget(null)}
      />

      <DetailDrawer
        open={Boolean(apiKeyProvider)}
        onClose={() => {
          if (!wooBusy) setApiKeyProvider(null);
        }}
        title={
          apiKeyProvider === "servicetitan"
            ? "Connect ServiceTitan"
            : "Connect WooCommerce"
        }
      >
        <form className="space-y-3" onSubmit={onApiKeyConnect}>
          <Field
            label={
              apiKeyProvider === "servicetitan" ? "ST Tenant ID" : "Store URL"
            }
          >
            <Input
              value={wooStore}
              onChange={(e) => setWooStore(e.target.value)}
              placeholder={
                apiKeyProvider === "servicetitan"
                  ? "123456789"
                  : "https://store.example.com"
              }
              required
            />
          </Field>
          <Field
            label={
              apiKeyProvider === "servicetitan" ? "Client ID" : "Consumer key"
            }
          >
            <Input
              value={wooKey}
              onChange={(e) => setWooKey(e.target.value)}
              required
              autoComplete="off"
            />
          </Field>
          <Field
            label={
              apiKeyProvider === "servicetitan"
                ? "Client secret"
                : "Consumer secret"
            }
          >
            <Input
              type="password"
              value={wooSecret}
              onChange={(e) => setWooSecret(e.target.value)}
              required
              autoComplete="off"
            />
          </Field>
          <Button type="submit" disabled={wooBusy}>
            {wooBusy ? "Connecting…" : "Connect"}
          </Button>
        </form>
      </DetailDrawer>

      <DetailDrawer
        open={shopifyOpen}
        onClose={() => {
          if (!wooBusy) setShopifyOpen(false);
        }}
        title="Connect Shopify"
      >
        <form className="space-y-3" onSubmit={onShopifyConnect}>
          <Field label="Shop domain">
            <Input
              value={shopifyShop}
              onChange={(e) => setShopifyShop(e.target.value)}
              placeholder="store.myshopify.com"
              required
            />
          </Field>
          <Button type="submit" disabled={wooBusy}>
            Continue to Shopify
          </Button>
        </form>
      </DetailDrawer>
    </AppShell>
  );
}

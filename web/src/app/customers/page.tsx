"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, Users } from "lucide-react";
import { AppShell } from "@/components/shell";
import {
  createCrmCustomer,
  listCrmCustomers,
  type Customer,
} from "@/lib/api/customers";
import { useAuth } from "@/lib/use-auth";
import { customers as copy, errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Button,
  DataTable,
  DetailDrawer,
  EmptyState,
  ErrorState,
  Field,
  FilterBar,
  ForbiddenState,
  Input,
  LoadingSkeleton,
  PageHeader,
  SearchInput,
  Select,
  StatusPill,
  Textarea,
  type DataTableColumn,
  useToast,
} from "@/components/ui";

const CREATE_FORM_ID = "create-customer-form";

type CreateForm = {
  name: string;
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  status: string;
};

function emptyCreateForm(): CreateForm {
  return {
    name: "",
    first_name: "",
    last_name: "",
    phone: "",
    email: "",
    address: "",
    notes: "",
    status: "ACTIVE",
  };
}

function formatUpdated(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function displayName(c: Customer) {
  return c.display_name || c.name || "Untitled customer";
}

export default function CustomersPage() {
  const router = useRouter();
  const { user, loading, forbidden, can } = useAuth({
    permission: "customers.read",
  });
  const toast = useToast();
  const canCreate = can("customers.create");

  const [rows, setRows] = useState<Customer[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [archiveFilter, setArchiveFilter] = useState<"active" | "all">("active");
  const [fetching, setFetching] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(emptyCreateForm);
  const [createBusy, setCreateBusy] = useState(false);

  useEffect(() => {
    const id = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(id);
  }, [search]);

  const load = useCallback(
    async (opts?: { cursor?: string; append?: boolean }) => {
      const data = await listCrmCustomers({
        q: debouncedSearch || undefined,
        status: statusFilter || undefined,
        include_archived: archiveFilter === "all",
        limit: 50,
        cursor: opts?.cursor,
      });
      const customers = data.customers || [];
      setRows((prev) => (opts?.append ? [...prev, ...customers] : customers));
      setNextCursor(data.next_cursor ?? null);
    },
    [debouncedSearch, statusFilter, archiveFilter],
  );

  useEffect(() => {
    if (!user || forbidden) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setFetching(true);
      setError(null);
      load()
        .catch((e) => setError(safeUserError(e, errors.loadFailed)))
        .finally(() => {
          if (!cancelled) setFetching(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [user, forbidden, load]);

  async function onLoadMore() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    setError(null);
    try {
      await load({ cursor: nextCursor, append: true });
    } catch (e) {
      setError(safeUserError(e, errors.loadFailed));
    } finally {
      setLoadingMore(false);
    }
  }

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setCreateBusy(true);
    setError(null);
    try {
      const name =
        createForm.name.trim() ||
        [createForm.first_name, createForm.last_name]
          .map((s) => s.trim())
          .filter(Boolean)
          .join(" ");
      if (!name) {
        throw new Error("Name is required.");
      }
      const { customer } = await createCrmCustomer({
        name,
        first_name: createForm.first_name.trim() || null,
        last_name: createForm.last_name.trim() || null,
        phone: createForm.phone.trim() || null,
        email: createForm.email.trim() || null,
        address: createForm.address.trim() || null,
        notes: createForm.notes.trim() || null,
        status: createForm.status || "ACTIVE",
      });
      toast.push("Customer created", "success");
      setCreateOpen(false);
      setCreateForm(emptyCreateForm());
      router.push(`/customers/${customer.id}`);
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setCreateBusy(false);
    }
  }

  const columns: DataTableColumn<Customer>[] = [
    {
      id: "name",
      header: "Customer",
      cell: (c) => (
        <div>
          <p className="font-medium">
            <Link
              href={`/customers/${c.id}`}
              className="hover:text-brand"
              onClick={(e) => e.stopPropagation()}
            >
              {displayName(c)}
            </Link>
          </p>
          {c.email ? (
            <p className="text-xs text-text-muted">{c.email}</p>
          ) : null}
        </div>
      ),
    },
    {
      id: "phones",
      header: "Phones",
      cell: (c) => (
        <span className="text-text-secondary">
          {c.phones?.length ? c.phones.join(", ") : "—"}
        </span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (c) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <StatusPill status={c.status} />
          {c.archived_at ? <StatusPill status="archived" /> : null}
        </div>
      ),
      className: "w-36",
    },
    {
      id: "address",
      header: "Address",
      cell: (c) => (
        <span className="text-text-secondary">{c.address || "—"}</span>
      ),
    },
    {
      id: "tags",
      header: "Tags",
      cell: (c) => (
        <span className="text-xs text-text-muted">
          {c.tags?.length ? c.tags.map((t) => t.name).join(", ") : "—"}
        </span>
      ),
    },
    {
      id: "updated",
      header: "Updated",
      cell: (c) => (
        <span className="text-xs text-text-muted">
          {formatUpdated(c.updated_at)}
        </span>
      ),
      className: "w-28",
    },
  ];

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
          canCreate ? (
            <Button
              onClick={() => {
                setCreateForm(emptyCreateForm());
                setCreateOpen(true);
              }}
            >
              <Plus className="size-4" aria-hidden />
              {copy.create}
            </Button>
          ) : null
        }
      />

      <FilterBar>
        <SearchInput
          className="w-full sm:w-64"
          placeholder="Search customers…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch("")}
        />
        <Select
          className="w-auto min-w-[8rem]"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Status filter"
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="INACTIVE">Inactive</option>
        </Select>
        <Select
          className="w-auto min-w-[9rem]"
          value={archiveFilter}
          onChange={(e) =>
            setArchiveFilter(e.target.value === "all" ? "all" : "active")
          }
          aria-label="Archive filter"
        >
          <option value="active">Hide archived</option>
          <option value="all">Include archived</option>
        </Select>
      </FilterBar>

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => {
            setError(null);
            setFetching(true);
            load()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      ) : null}

      {fetching ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={rows}
            onRowClick={(c) => router.push(`/customers/${c.id}`)}
            empty={
              <EmptyState
                icon={<Users className="size-8" />}
                title={
                  debouncedSearch || statusFilter
                    ? "No matching customers"
                    : copy.empty
                }
                description={
                  debouncedSearch || statusFilter
                    ? "Try a different search or filter."
                    : copy.emptyHint
                }
              />
            }
          />
          {nextCursor ? (
            <div className="mt-4 flex justify-center">
              <Button
                variant="secondary"
                disabled={loadingMore}
                onClick={() => {
                  void onLoadMore();
                }}
              >
                {loadingMore ? "Loading…" : "Load more"}
              </Button>
            </div>
          ) : null}
        </>
      )}

      <DetailDrawer
        open={createOpen}
        onClose={() => {
          if (createBusy) return;
          setCreateOpen(false);
        }}
        title={copy.create}
        description="Add a customer record for your business."
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
          <Field label="Name" hint="Required if first/last name omitted">
            <Input
              value={createForm.name}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, name: e.target.value }))
              }
              placeholder="Display name"
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="First name">
              <Input
                value={createForm.first_name}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, first_name: e.target.value }))
                }
              />
            </Field>
            <Field label="Last name">
              <Input
                value={createForm.last_name}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, last_name: e.target.value }))
                }
              />
            </Field>
          </div>
          <Field label="Phone">
            <Input
              type="tel"
              value={createForm.phone}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, phone: e.target.value }))
              }
              placeholder="+1…"
            />
          </Field>
          <Field label="Email">
            <Input
              type="email"
              value={createForm.email}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, email: e.target.value }))
              }
            />
          </Field>
          <Field label="Address">
            <Input
              value={createForm.address}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, address: e.target.value }))
              }
            />
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
          <Field label="Notes">
            <Textarea
              rows={3}
              value={createForm.notes}
              onChange={(e) =>
                setCreateForm((f) => ({ ...f, notes: e.target.value }))
              }
            />
          </Field>
        </form>
      </DetailDrawer>
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, MapPin, Plus, X } from "lucide-react";
import { AppShell } from "@/components/shell";
import { formatWhen } from "@/lib/api";
import {
  addCrmCustomerNote,
  addCrmCustomerTag,
  archiveCrmCustomer,
  archiveCrmCustomerLocation,
  createCrmCustomerLocation,
  getCrmCustomer,
  getCrmCustomerTimeline,
  removeCrmCustomerTag,
  restoreCrmCustomer,
  setPrimaryCrmCustomerLocation,
  updateCrmCustomer,
  updateCrmCustomerLocation,
  type Customer,
  type CustomerLocation,
  type CustomerTimelineEvent,
  type LocationCreateBody,
} from "@/lib/api/customers";
import {
  getCustomerMembership,
  type CustomerMembership,
} from "@/lib/api/memberships";
import { useAuth } from "@/lib/use-auth";
import { customers as copy, errors } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";
import {
  Breadcrumbs,
  Button,
  ConfirmDialog,
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
  Timeline,
  useToast,
} from "@/components/ui";

const PROFILE_FORM_ID = "customer-profile-form";
const LOCATION_FORM_ID = "customer-location-form";

type ProfileForm = {
  name: string;
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  address: string;
  notes: string;
  status: string;
};

type LocationForm = {
  label: string;
  address_line_1: string;
  address_line_2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  access_instructions: string;
  is_primary: boolean;
};

function emptyLocationForm(): LocationForm {
  return {
    label: "",
    address_line_1: "",
    address_line_2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "",
    access_instructions: "",
    is_primary: false,
  };
}

function toProfileForm(c: Customer): ProfileForm {
  return {
    name: c.name || "",
    first_name: c.first_name || "",
    last_name: c.last_name || "",
    phone: c.phones?.[0] || "",
    email: c.email || "",
    address: c.address || "",
    notes: c.notes || "",
    status: c.status || "ACTIVE",
  };
}

function toLocationForm(loc: CustomerLocation): LocationForm {
  return {
    label: loc.label || "",
    address_line_1: loc.address_line_1 || "",
    address_line_2: loc.address_line_2 || "",
    city: loc.city || "",
    state: loc.state || "",
    postal_code: loc.postal_code || "",
    country: loc.country || "",
    access_instructions: loc.access_instructions || "",
    is_primary: Boolean(loc.is_primary),
  };
}

function formatLocationLine(loc: CustomerLocation) {
  return [
    loc.address_line_1,
    loc.address_line_2,
    [loc.city, loc.state, loc.postal_code].filter(Boolean).join(", "),
    loc.country,
  ]
    .filter(Boolean)
    .join(" · ");
}

function timelineTone(
  type: string,
): "default" | "success" | "warn" | "danger" {
  switch (type) {
    case "CALL":
      return "default";
    case "JOB":
      return "success";
    case "APPOINTMENT":
      return "warn";
    case "NOTE":
      return "default";
    default:
      return "default";
  }
}

/** PATCH/archive responses omit locations — keep the last known list. */
function mergeCustomer(prev: Customer | null, next: Customer): Customer {
  return {
    ...next,
    locations: next.locations ?? prev?.locations,
    phones: next.phones ?? prev?.phones ?? [],
    tags: next.tags ?? prev?.tags ?? [],
  };
}

export default function CustomerDetailPage() {
  const params = useParams<{ id: string }>();
  const { user, loading, forbidden, can } = useAuth({
    permission: "customers.read",
  });
  const toast = useToast();
  const canUpdate = can("customers.update");
  const canDelete = can("customers.delete");

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [membership, setMembership] = useState<CustomerMembership | null>(null);
  const [timeline, setTimeline] = useState<CustomerTimelineEvent[]>([]);
  const [profile, setProfile] = useState<ProfileForm | null>(null);
  const [tagInput, setTagInput] = useState("");
  const [noteInput, setNoteInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);
  const [saveBusy, setSaveBusy] = useState(false);
  const [tagBusy, setTagBusy] = useState(false);
  const [noteBusy, setNoteBusy] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveBusy, setArchiveBusy] = useState(false);

  const [locationOpen, setLocationOpen] = useState(false);
  const [editingLocationId, setEditingLocationId] = useState<string | null>(
    null,
  );
  const [locationForm, setLocationForm] =
    useState<LocationForm>(emptyLocationForm);
  const [locationBusy, setLocationBusy] = useState(false);
  const [locationArchiveId, setLocationArchiveId] = useState<string | null>(
    null,
  );
  const [locationArchiveBusy, setLocationArchiveBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [custRes, timelineRes, membershipRes] = await Promise.all([
      getCrmCustomer(params.id),
      getCrmCustomerTimeline(params.id, { limit: 50 }),
      getCustomerMembership(params.id).catch(() => ({ membership: null })),
    ]);
    setCustomer(custRes.customer);
    setProfile(toProfileForm(custRes.customer));
    setTimeline(timelineRes.items || []);
    setMembership(membershipRes.membership);
  }, [params.id]);

  useEffect(() => {
    if (!user || forbidden) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setFetching(true);
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

  const locations = useMemo(
    () => (customer?.locations || []).filter((l) => !l.archived_at),
    [customer],
  );

  const timelineItems = useMemo(
    () =>
      timeline.map((ev) => ({
        id: ev.source_key || `${ev.type}:${ev.id}`,
        title: ev.title || ev.type,
        detail: ev.summary || undefined,
        time: formatWhen(ev.timestamp),
        tone: timelineTone(ev.type),
      })),
    [timeline],
  );

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    if (!customer || !profile) return;
    setSaveBusy(true);
    setError(null);
    try {
      const { customer: updated } = await updateCrmCustomer(customer.id, {
        name: profile.name.trim() || null,
        first_name: profile.first_name.trim() || null,
        last_name: profile.last_name.trim() || null,
        phone: profile.phone.trim() || null,
        email: profile.email.trim() || null,
        address: profile.address.trim() || null,
        notes: profile.notes.trim() || null,
        status: profile.status || "ACTIVE",
      });
      const merged = mergeCustomer(customer, updated);
      setCustomer(merged);
      setProfile(toProfileForm(merged));
      toast.push("Customer updated", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setSaveBusy(false);
    }
  }

  async function onAddTag(e: FormEvent) {
    e.preventDefault();
    if (!customer || !tagInput.trim()) return;
    setTagBusy(true);
    setError(null);
    try {
      const { customer: updated } = await addCrmCustomerTag(
        customer.id,
        tagInput.trim(),
      );
      setCustomer(mergeCustomer(customer, updated));
      setTagInput("");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setTagBusy(false);
    }
  }

  async function onRemoveTag(tagId: string) {
    if (!customer) return;
    setError(null);
    try {
      const { customer: updated } = await removeCrmCustomerTag(
        customer.id,
        tagId,
      );
      setCustomer(mergeCustomer(customer, updated));
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    }
  }

  async function onAddNote(e: FormEvent) {
    e.preventDefault();
    if (!customer || !noteInput.trim()) return;
    setNoteBusy(true);
    setError(null);
    try {
      await addCrmCustomerNote(customer.id, noteInput.trim());
      setNoteInput("");
      const timelineRes = await getCrmCustomerTimeline(customer.id, {
        limit: 50,
      });
      setTimeline(timelineRes.items || []);
      toast.push("Note added", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setNoteBusy(false);
    }
  }

  async function onArchive() {
    if (!customer) return;
    setArchiveBusy(true);
    setError(null);
    try {
      const { customer: updated } = await archiveCrmCustomer(customer.id);
      const merged = mergeCustomer(customer, updated);
      setCustomer(merged);
      setProfile(toProfileForm(merged));
      setArchiveOpen(false);
      toast.push("Customer archived", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setArchiveBusy(false);
    }
  }

  async function onRestore() {
    if (!customer) return;
    setArchiveBusy(true);
    setError(null);
    try {
      const { customer: updated } = await restoreCrmCustomer(customer.id);
      const merged = mergeCustomer(customer, updated);
      setCustomer(merged);
      setProfile(toProfileForm(merged));
      toast.push("Customer restored", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setArchiveBusy(false);
    }
  }

  function openCreateLocation() {
    setEditingLocationId(null);
    setLocationForm({
      ...emptyLocationForm(),
      is_primary: locations.length === 0,
    });
    setLocationOpen(true);
  }

  function openEditLocation(loc: CustomerLocation) {
    setEditingLocationId(loc.id);
    setLocationForm(toLocationForm(loc));
    setLocationOpen(true);
  }

  async function onSaveLocation(e: FormEvent) {
    e.preventDefault();
    if (!customer) return;
    if (!locationForm.address_line_1.trim()) {
      setError("Address line 1 is required.");
      return;
    }
    setLocationBusy(true);
    setError(null);
    try {
      const body: LocationCreateBody = {
        label: locationForm.label.trim() || null,
        address_line_1: locationForm.address_line_1.trim(),
        address_line_2: locationForm.address_line_2.trim() || null,
        city: locationForm.city.trim() || null,
        state: locationForm.state.trim() || null,
        postal_code: locationForm.postal_code.trim() || null,
        country: locationForm.country.trim() || null,
        access_instructions: locationForm.access_instructions.trim() || null,
        is_primary: locationForm.is_primary,
      };
      if (editingLocationId) {
        await updateCrmCustomerLocation(
          customer.id,
          editingLocationId,
          body,
        );
      } else {
        await createCrmCustomerLocation(customer.id, body);
      }
      setLocationOpen(false);
      await refresh();
      toast.push(
        editingLocationId ? "Location updated" : "Location added",
        "success",
      );
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setLocationBusy(false);
    }
  }

  async function onSetPrimary(locationId: string) {
    if (!customer) return;
    setError(null);
    try {
      await setPrimaryCrmCustomerLocation(customer.id, locationId);
      await refresh();
      toast.push("Primary location updated", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    }
  }

  async function onArchiveLocation() {
    if (!customer || !locationArchiveId) return;
    setLocationArchiveBusy(true);
    setError(null);
    try {
      await archiveCrmCustomerLocation(customer.id, locationArchiveId);
      setLocationArchiveId(null);
      await refresh();
      toast.push("Location archived", "success");
    } catch (err) {
      setError(safeUserError(err, errors.saveFailed));
    } finally {
      setLocationArchiveBusy(false);
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

  if (fetching && !customer) {
    return (
      <AppShell user={user}>
        <LoadingSkeleton rows={6} />
      </AppShell>
    );
  }

  if (!customer || !profile) {
    return (
      <AppShell user={user}>
        <ErrorState
          title={copy.notFound}
          message={error || "Unable to load this customer."}
          onRetry={() => {
            setFetching(true);
            refresh()
              .catch((e) => setError(safeUserError(e, errors.loadFailed)))
              .finally(() => setFetching(false));
          }}
        />
      </AppShell>
    );
  }

  const title = customer.display_name || customer.name;

  return (
    <AppShell user={user}>
      <Breadcrumbs
        items={[
          { label: copy.title, href: "/customers" },
          { label: title },
        ]}
      />

      <PageHeader
        className="mt-3"
        title={title}
        description={[customer.email, customer.phones?.[0]]
          .filter(Boolean)
          .join(" · ")}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={customer.status} />
            {customer.archived_at ? <StatusPill status="archived" /> : null}
            {canDelete && !customer.archived_at ? (
              <Button variant="danger" onClick={() => setArchiveOpen(true)}>
                Archive
              </Button>
            ) : null}
            {canUpdate && customer.archived_at ? (
              <Button
                variant="ink"
                disabled={archiveBusy}
                onClick={() => {
                  void onRestore();
                }}
              >
                {archiveBusy ? "Restoring…" : "Restore"}
              </Button>
            ) : null}
          </div>
        }
      />

      <Link
        href="/customers"
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-brand"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Back to customers
      </Link>

      {error ? (
        <ErrorState
          className="mb-4"
          message={error}
          onRetry={() => setError(null)}
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Surface className="p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-text-primary">Overview</h3>
            {canUpdate ? (
              <Button
                type="submit"
                form={PROFILE_FORM_ID}
                variant="ink"
                size="sm"
                disabled={saveBusy || Boolean(customer.archived_at)}
              >
                {saveBusy ? "Saving…" : "Save"}
              </Button>
            ) : null}
          </div>
          <form
            id={PROFILE_FORM_ID}
            className="mt-3 space-y-3"
            onSubmit={onSaveProfile}
          >
            <Field label="Name">
              <Input
                value={profile.name}
                disabled={!canUpdate || Boolean(customer.archived_at)}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, name: e.target.value } : f))
                }
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="First name">
                <Input
                  value={profile.first_name}
                  disabled={!canUpdate || Boolean(customer.archived_at)}
                  onChange={(e) =>
                    setProfile((f) =>
                      f ? { ...f, first_name: e.target.value } : f,
                    )
                  }
                />
              </Field>
              <Field label="Last name">
                <Input
                  value={profile.last_name}
                  disabled={!canUpdate || Boolean(customer.archived_at)}
                  onChange={(e) =>
                    setProfile((f) =>
                      f ? { ...f, last_name: e.target.value } : f,
                    )
                  }
                />
              </Field>
            </div>
            <Field label="Phone">
              <Input
                type="tel"
                value={profile.phone}
                disabled={!canUpdate || Boolean(customer.archived_at)}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, phone: e.target.value } : f))
                }
              />
            </Field>
            <Field label="Email">
              <Input
                type="email"
                value={profile.email}
                disabled={!canUpdate || Boolean(customer.archived_at)}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, email: e.target.value } : f))
                }
              />
            </Field>
            <Field label="Address">
              <Input
                value={profile.address}
                disabled={!canUpdate || Boolean(customer.archived_at)}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, address: e.target.value } : f))
                }
              />
            </Field>
            <Field label="Status">
              <Select
                value={profile.status}
                disabled={!canUpdate || Boolean(customer.archived_at)}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, status: e.target.value } : f))
                }
              >
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </Select>
            </Field>
            <Field label="Notes">
              <Textarea
                rows={3}
                value={profile.notes}
                disabled={!canUpdate || Boolean(customer.archived_at)}
                onChange={(e) =>
                  setProfile((f) => (f ? { ...f, notes: e.target.value } : f))
                }
              />
            </Field>
          </form>
        </Surface>

        <div className="space-y-4">
          <Surface className="p-4">
            <h3 className="text-sm font-semibold text-text-primary">Tags</h3>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {(customer.tags || []).map((tag) => (
                <span
                  key={tag.id}
                  className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-muted px-2 py-0.5 text-xs text-text-secondary"
                >
                  {tag.name}
                  {canUpdate && !customer.archived_at ? (
                    <button
                      type="button"
                      className="rounded p-0.5 hover:text-danger"
                      aria-label={`Remove tag ${tag.name}`}
                      onClick={() => {
                        void onRemoveTag(tag.id);
                      }}
                    >
                      <X className="size-3" />
                    </button>
                  ) : null}
                </span>
              ))}
              {(customer.tags || []).length === 0 ? (
                <span className="text-sm text-text-muted">No tags</span>
              ) : null}
            </div>
            {canUpdate && !customer.archived_at ? (
              <form
                className="mt-3 flex gap-2"
                onSubmit={onAddTag}
              >
                <Input
                  className="flex-1"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  placeholder="Add a tag"
                />
                <Button type="submit" variant="ink" disabled={tagBusy}>
                  {tagBusy ? "Adding…" : "Add"}
                </Button>
              </form>
            ) : null}
          </Surface>

          <Surface className="p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-text-primary">
                Locations
              </h3>
              {canUpdate && !customer.archived_at ? (
                <Button size="sm" onClick={openCreateLocation}>
                  <Plus className="size-3.5" aria-hidden />
                  Add
                </Button>
              ) : null}
            </div>
            <ul className="mt-3 space-y-3">
              {locations.map((loc) => (
                <li
                  key={loc.id}
                  className="rounded-md border border-border px-3 py-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
                        <MapPin className="size-3.5 shrink-0 text-text-muted" />
                        {loc.label || "Location"}
                        {loc.is_primary ? (
                          <span className="text-xs font-normal text-brand">
                            Primary
                          </span>
                        ) : null}
                      </p>
                      <p className="mt-1 text-sm text-text-secondary">
                        {formatLocationLine(loc)}
                      </p>
                      {loc.access_instructions ? (
                        <p className="mt-1 text-xs text-text-muted">
                          {loc.access_instructions}
                        </p>
                      ) : null}
                    </div>
                    {canUpdate && !customer.archived_at ? (
                      <div className="flex shrink-0 flex-col gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => openEditLocation(loc)}
                        >
                          Edit
                        </Button>
                        {!loc.is_primary ? (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              void onSetPrimary(loc.id);
                            }}
                          >
                            Set primary
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setLocationArchiveId(loc.id)}
                        >
                          Archive
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </li>
              ))}
              {locations.length === 0 ? (
                <li className="text-sm text-text-muted">
                  No locations yet.
                </li>
              ) : null}
            </ul>
          </Surface>
        </div>
      </div>

      <Surface className="mt-4 p-4">
        <h3 className="text-sm font-semibold text-text-primary">Membership</h3>
        <div className="mt-3 text-sm">
          {membership ? (
            <div className="flex flex-wrap items-center gap-3">
              <StatusPill status={membership.status} />
              <span>{membership.plan?.name || membership.plan_id.slice(0, 8)}</span>
              <span className="text-text-muted">{membership.billing_interval}</span>
              <span className="text-text-muted">
                through {new Date(membership.current_period_end).toLocaleDateString()}
              </span>
              <Link
                href={`/crm/memberships/${membership.id}`}
                className="underline-offset-2 hover:underline"
              >
                View
              </Link>
            </div>
          ) : (
            <p className="text-text-muted">No open membership.</p>
          )}
        </div>
      </Surface>

      <Surface className="mt-4 p-4">
        <h3 className="text-sm font-semibold text-text-primary">Timeline</h3>
        <div className="mt-3">
          {timelineItems.length === 0 ? (
            <EmptyState
              title={copy.timelineEmpty}
              description={copy.timelineEmptyHint}
            />
          ) : (
            <Timeline items={timelineItems} />
          )}
        </div>
        {canUpdate && !customer.archived_at ? (
          <form
            className="mt-4 flex gap-2"
            onSubmit={onAddNote}
          >
            <Input
              className="flex-1"
              value={noteInput}
              onChange={(e) => setNoteInput(e.target.value)}
              placeholder="Add a note to the timeline"
              required
            />
            <Button type="submit" variant="ink" disabled={noteBusy}>
              {noteBusy ? "Adding…" : "Add note"}
            </Button>
          </form>
        ) : null}
      </Surface>

      <DetailDrawer
        open={locationOpen}
        onClose={() => {
          if (locationBusy) return;
          setLocationOpen(false);
        }}
        title={editingLocationId ? "Edit location" : "Add location"}
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              disabled={locationBusy}
              onClick={() => setLocationOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              form={LOCATION_FORM_ID}
              variant="ink"
              disabled={locationBusy}
            >
              {locationBusy ? "Saving…" : "Save"}
            </Button>
          </div>
        }
      >
        <form
          id={LOCATION_FORM_ID}
          className="space-y-3"
          onSubmit={onSaveLocation}
        >
          <Field label="Label">
            <Input
              value={locationForm.label}
              onChange={(e) =>
                setLocationForm((f) => ({ ...f, label: e.target.value }))
              }
              placeholder="Home, Office…"
            />
          </Field>
          <Field label="Address line 1">
            <Input
              required
              value={locationForm.address_line_1}
              onChange={(e) =>
                setLocationForm((f) => ({
                  ...f,
                  address_line_1: e.target.value,
                }))
              }
            />
          </Field>
          <Field label="Address line 2">
            <Input
              value={locationForm.address_line_2}
              onChange={(e) =>
                setLocationForm((f) => ({
                  ...f,
                  address_line_2: e.target.value,
                }))
              }
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="City">
              <Input
                value={locationForm.city}
                onChange={(e) =>
                  setLocationForm((f) => ({ ...f, city: e.target.value }))
                }
              />
            </Field>
            <Field label="State">
              <Input
                value={locationForm.state}
                onChange={(e) =>
                  setLocationForm((f) => ({ ...f, state: e.target.value }))
                }
              />
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Postal code">
              <Input
                value={locationForm.postal_code}
                onChange={(e) =>
                  setLocationForm((f) => ({
                    ...f,
                    postal_code: e.target.value,
                  }))
                }
              />
            </Field>
            <Field label="Country">
              <Input
                value={locationForm.country}
                onChange={(e) =>
                  setLocationForm((f) => ({ ...f, country: e.target.value }))
                }
                placeholder="US"
              />
            </Field>
          </div>
          <Field label="Access instructions">
            <Textarea
              rows={3}
              value={locationForm.access_instructions}
              onChange={(e) =>
                setLocationForm((f) => ({
                  ...f,
                  access_instructions: e.target.value,
                }))
              }
            />
          </Field>
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={locationForm.is_primary}
              onChange={(e) =>
                setLocationForm((f) => ({
                  ...f,
                  is_primary: e.target.checked,
                }))
              }
            />
            Primary location
          </label>
        </form>
      </DetailDrawer>

      <ConfirmDialog
        open={archiveOpen}
        title="Archive this customer?"
        description={`${title} will be archived and hidden from the default list. You can restore them later.`}
        confirmLabel="Archive"
        danger
        busy={archiveBusy}
        onConfirm={() => {
          void onArchive();
        }}
        onCancel={() => {
          if (archiveBusy) return;
          setArchiveOpen(false);
        }}
      />

      <ConfirmDialog
        open={Boolean(locationArchiveId)}
        title="Archive this location?"
        description="The location will be removed from the active list."
        confirmLabel="Archive"
        danger
        busy={locationArchiveBusy}
        onConfirm={() => {
          void onArchiveLocation();
        }}
        onCancel={() => {
          if (locationArchiveBusy) return;
          setLocationArchiveId(null);
        }}
      />
    </AppShell>
  );
}

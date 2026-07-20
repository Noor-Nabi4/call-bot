"use client";

import {
  Button,
  DetailDrawer,
  Field,
  Input,
  Select,
} from "@/components/ui";
import type { CustomerOption } from "@/types";

export type CreateJobForm = {
  customer_id: string;
  service_type: string;
  scheduled_starts_at: string;
};

export const EMPTY_JOB_FORM: CreateJobForm = {
  customer_id: "",
  service_type: "",
  scheduled_starts_at: "",
};

export function CreateJobDrawer({
  open,
  onClose,
  form,
  onChange,
  onSubmit,
  busy,
  customers,
  formId = "create-job-form",
  emptyHint,
}: {
  open: boolean;
  onClose: () => void;
  form: CreateJobForm;
  onChange: (next: CreateJobForm) => void;
  onSubmit: (e: React.FormEvent) => void;
  busy: boolean;
  customers: CustomerOption[];
  formId?: string;
  emptyHint?: string;
}) {
  return (
    <DetailDrawer
      open={open}
      onClose={onClose}
      title="Create job"
      description="Create a new job for an existing customer."
      width="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form={formId} type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create job"}
          </Button>
        </div>
      }
    >
      <form id={formId} onSubmit={onSubmit} className="grid gap-3">
        <Field label="Customer">
          <Select
            value={form.customer_id}
            onChange={(e) =>
              onChange({ ...form, customer_id: e.target.value })
            }
            required
          >
            <option value="">Select customer…</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Service type">
          <Input
            value={form.service_type}
            onChange={(e) =>
              onChange({ ...form, service_type: e.target.value })
            }
            required
            placeholder="e.g. AC repair"
          />
        </Field>
        <Field label="Scheduled start" hint="Optional">
          <Input
            type="datetime-local"
            value={form.scheduled_starts_at}
            onChange={(e) =>
              onChange({
                ...form,
                scheduled_starts_at: e.target.value,
              })
            }
          />
        </Field>
        {customers.length === 0 && emptyHint ? (
          <p className="text-xs text-text-muted">{emptyHint}</p>
        ) : null}
      </form>
    </DetailDrawer>
  );
}

"use client";

import {
  Button,
  DetailDrawer,
  Field,
  Input,
} from "@/components/ui";

export type CreateTechForm = {
  name: string;
  email: string;
  password: string;
  phone: string;
};

export const EMPTY_TECH_FORM: CreateTechForm = {
  name: "",
  email: "",
  password: "",
  phone: "",
};

export function CreateTechDrawer({
  open,
  onClose,
  form,
  onChange,
  onSubmit,
  busy,
  formId = "create-tech-form",
}: {
  open: boolean;
  onClose: () => void;
  form: CreateTechForm;
  onChange: (next: CreateTechForm) => void;
  onSubmit: (e: React.FormEvent) => void;
  busy: boolean;
  formId?: string;
}) {
  return (
    <DetailDrawer
      open={open}
      onClose={onClose}
      title="Add technician"
      description="Create a field technician account for your organization."
      width="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button form={formId} type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create"}
          </Button>
        </div>
      }
    >
      <form id={formId} onSubmit={onSubmit} className="grid gap-3">
        <Field label="Name">
          <Input
            value={form.name}
            onChange={(e) => onChange({ ...form, name: e.target.value })}
            required
          />
        </Field>
        <Field label="Email">
          <Input
            type="email"
            value={form.email}
            onChange={(e) => onChange({ ...form, email: e.target.value })}
            required
          />
        </Field>
        <Field label="Password" hint="Minimum 8 characters">
          <Input
            type="password"
            value={form.password}
            onChange={(e) => onChange({ ...form, password: e.target.value })}
            required
            minLength={8}
          />
        </Field>
        <Field label="Phone">
          <Input
            value={form.phone}
            onChange={(e) => onChange({ ...form, phone: e.target.value })}
            placeholder="Optional"
          />
        </Field>
      </form>
    </DetailDrawer>
  );
}

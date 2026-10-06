"use client";

import type { ChangeEvent } from "react";

export type CrmFieldDef = {
  id: string;
  field_key: string;
  label: string;
  field_type: string;
  required?: boolean;
  enabled?: boolean;
  configuration?: { options?: string[] };
  default_value?: unknown;
};

type Props = {
  field: CrmFieldDef;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled?: boolean;
};

export function FieldRenderer({ field, value, onChange, disabled }: Props) {
  const id = `field-${field.field_key}`;
  const label = (
    <label htmlFor={id} className="mb-1 block text-sm font-medium text-text-primary">
      {field.label}
      {field.required ? <span className="text-danger"> *</span> : null}
    </label>
  );
  const base =
    "w-full rounded-[var(--radius-md)] border border-border bg-surface px-3 py-2 text-sm";

  const setText = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    onChange(e.target.value);

  switch (field.field_type) {
    case "BOOLEAN":
      return (
        <div>
          {label}
          <input
            id={id}
            type="checkbox"
            checked={Boolean(value)}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
          />
        </div>
      );
    case "NUMBER":
    case "CURRENCY":
      return (
        <div>
          {label}
          <input
            id={id}
            className={base}
            type="number"
            step={field.field_type === "CURRENCY" ? "0.01" : "any"}
            value={value === null || value === undefined ? "" : String(value)}
            disabled={disabled}
            onChange={(e) =>
              onChange(e.target.value === "" ? null : Number(e.target.value))
            }
          />
        </div>
      );
    case "DATE":
      return (
        <div>
          {label}
          <input
            id={id}
            className={base}
            type="date"
            value={typeof value === "string" ? value.slice(0, 10) : ""}
            disabled={disabled}
            onChange={setText}
          />
        </div>
      );
    case "DATETIME":
      return (
        <div>
          {label}
          <input
            id={id}
            className={base}
            type="datetime-local"
            value={typeof value === "string" ? value.slice(0, 16) : ""}
            disabled={disabled}
            onChange={setText}
          />
        </div>
      );
    case "DROPDOWN":
      return (
        <div>
          {label}
          <select
            id={id}
            className={base}
            value={typeof value === "string" ? value : ""}
            disabled={disabled}
            onChange={setText}
          >
            <option value="">Select…</option>
            {(field.configuration?.options || []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </div>
      );
    case "MULTI_SELECT": {
      const selected = Array.isArray(value) ? (value as string[]) : [];
      return (
        <div>
          {label}
          <div className="flex flex-col gap-1">
            {(field.configuration?.options || []).map((opt) => (
              <label key={opt} className="inline-flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selected.includes(opt)}
                  disabled={disabled}
                  onChange={(e) => {
                    if (e.target.checked) onChange([...selected, opt]);
                    else onChange(selected.filter((x) => x !== opt));
                  }}
                />
                {opt}
              </label>
            ))}
          </div>
        </div>
      );
    }
    case "TEXT":
    default:
      return (
        <div>
          {label}
          <input
            id={id}
            className={base}
            type={
              field.field_type === "EMAIL"
                ? "email"
                : field.field_type === "URL"
                  ? "url"
                  : field.field_type === "PHONE"
                    ? "tel"
                    : "text"
            }
            value={typeof value === "string" ? value : value == null ? "" : String(value)}
            disabled={disabled}
            onChange={setText}
          />
        </div>
      );
  }
}

export function DynamicForm({
  fields,
  values,
  onChange,
  disabled,
}: {
  fields: CrmFieldDef[];
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
  disabled?: boolean;
}) {
  return (
    <div className="grid gap-4">
      {fields
        .filter((f) => f.enabled !== false)
        .map((field) => (
          <FieldRenderer
            key={field.id || field.field_key}
            field={field}
            value={values[field.field_key]}
            disabled={disabled}
            onChange={(v) => onChange(field.field_key, v)}
          />
        ))}
    </div>
  );
}

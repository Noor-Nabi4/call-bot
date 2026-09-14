"use client";

import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { OpsUser } from "@/lib/api";
import { navFor } from "./nav";

export function CommandSearch({
  open,
  onClose,
  user,
}: {
  open: boolean;
  onClose: () => void;
  user: OpsUser;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  const handleClose = useCallback(() => {
    setQ("");
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, handleClose]);

  if (!open) return null;

  const destinations = navFor(user)
    .map((i) => ({ label: i.label, href: i.href }))
    .filter((d) => d.label.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="fixed inset-0 z-50 grid place-items-start justify-center px-4 pt-[12vh]">
      <button
        type="button"
        className="absolute inset-0 bg-text-primary/25"
        aria-label="Close search"
        onClick={handleClose}
      />
      <div
        role="dialog"
        aria-label="Search"
        className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow-elevated)]"
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="size-4 text-text-muted" aria-hidden />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Go to…"
            className="h-11 flex-1 bg-transparent text-sm outline-none"
          />
        </div>
        <ul className="max-h-64 overflow-y-auto py-1">
          {destinations.map((d) => (
            <li key={d.href}>
              <button
                type="button"
                className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                onClick={() => {
                  handleClose();
                  router.push(d.href);
                }}
              >
                {d.label}
              </button>
            </li>
          ))}
          {destinations.length === 0 ? (
            <li className="px-3 py-4 text-sm text-text-muted">No matches</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { Phone } from "lucide-react";
import { cn } from "@/lib/cn";
import { site } from "@/lib/copy";

export function TopNav({ active }: { active?: "voice" | "telephony" }) {
  return (
    <nav
      className="relative z-[1] flex items-center justify-between gap-4"
      aria-label="Main"
    >
      <Link href="/" className="group flex items-baseline gap-2 text-text-primary">
        <span className="font-display text-xl font-semibold tracking-tight sm:text-2xl">
          {site.brand}
        </span>
      </Link>
      <div className="flex items-center gap-1 rounded-full border border-border bg-surface-strong/80 p-1 text-sm">
        <Link
          href="/"
          className={cn(
            "rounded-full px-3 py-1.5 transition-colors duration-200",
            active === "voice"
              ? "bg-brand-soft text-brand-bright"
              : "text-text-secondary hover:text-text-primary",
          )}
          aria-current={active === "voice" ? "page" : undefined}
        >
          {site.navVoice}
        </Link>
        <Link
          href="/telephony"
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 transition-colors duration-200",
            active === "telephony"
              ? "bg-brand-soft text-brand-bright"
              : "text-text-secondary hover:text-text-primary",
          )}
          aria-current={active === "telephony" ? "page" : undefined}
        >
          <Phone className="size-3.5" aria-hidden />
          {site.navPhone}
        </Link>
      </div>
    </nav>
  );
}

export function PageShell({
  children,
  active,
}: {
  children: React.ReactNode;
  active?: "voice" | "telephony";
}) {
  return (
    <div className="relative isolate min-h-screen overflow-hidden">
      <div className="atmosphere absolute inset-0 -z-10" aria-hidden />
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-8 p-[clamp(1.25rem,4vw,2.5rem)]">
        <TopNav active={active} />
        {children}
      </div>
    </div>
  );
}

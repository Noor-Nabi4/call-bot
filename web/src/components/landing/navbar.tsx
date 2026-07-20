"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { Button } from "@/components/landing/button";
import { opsLoginUrl } from "@/lib/site-urls";

const links = [
  { href: "#platform", label: "Platform" },
  { href: "#features", label: "Features" },
  { href: "#industries", label: "Industries" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faq", label: "FAQ" },
] as const;

type NavbarProps = {
  brand: string;
  variant?: "hero" | "solid";
};

export function Navbar({ brand, variant = "hero" }: NavbarProps) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const panelId = useId();
  const solid = variant === "solid" || scrolled;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 transition-[background-color,border-color,backdrop-filter,box-shadow] duration-300 ${
        solid
          ? "border-b border-line bg-surface/90 shadow-[var(--shadow-sm)] backdrop-blur-md"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="content-width flex items-center justify-between gap-4 px-6 py-4 sm:px-10 lg:px-12">
        <Link
          href="/"
          className={`font-display text-xl font-semibold tracking-[-0.03em] no-underline sm:text-2xl ${
            solid ? "text-ink" : "text-white"
          }`}
        >
          {brand}
        </Link>

        <nav className="hidden items-center gap-1 lg:flex" aria-label="Primary">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={`rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors ${
                solid
                  ? "text-muted hover:bg-bg hover:text-ink"
                  : "text-hero-muted hover:bg-white/5 hover:text-white"
              }`}
            >
              {link.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 sm:flex">
          <a
            href={opsLoginUrl()}
            className={`rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors ${
              solid
                ? "text-muted hover:text-ink"
                : "text-hero-muted hover:text-white"
            }`}
          >
            Sign in
          </a>
          <Button href="/signup" variant={solid ? "primary" : "inverse"} size="md">
            Start Free Trial
          </Button>
        </div>

        <button
          type="button"
          className={`inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-sm)] lg:hidden ${
            solid
              ? "border border-line text-ink"
              : "border border-white/20 text-white"
          }`}
          aria-expanded={open}
          aria-controls={panelId}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="sr-only">{open ? "Close" : "Menu"}</span>
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            {open ? (
              <path
                d="M4 4l10 10M14 4L4 14"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
              />
            ) : (
              <path
                d="M3 5h12M3 9h12M3 13h12"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
              />
            )}
          </svg>
        </button>
      </div>

      {open ? (
        <div
          id={panelId}
          className="border-t border-line bg-surface px-6 py-4 shadow-[var(--shadow-md)] lg:hidden"
        >
          <nav aria-label="Mobile">
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {links.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="block rounded-[var(--radius-sm)] px-3 py-3 text-sm font-medium text-ink hover:bg-bg"
                    onClick={() => setOpen(false)}
                  >
                    {link.label}
                  </a>
                </li>
              ))}
              <li className="mt-2 grid gap-2 border-t border-line pt-4">
                <Button href={opsLoginUrl()} variant="secondary" className="w-full">
                  Sign in
                </Button>
                <Button href="/signup" variant="primary" className="w-full">
                  Start Free Trial
                </Button>
              </li>
            </ul>
          </nav>
        </div>
      ) : null}
    </header>
  );
}

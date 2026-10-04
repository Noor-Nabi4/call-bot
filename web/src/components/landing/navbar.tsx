"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { BrandLogo } from "@/components/landing/brand-logo";
import { Button } from "@/components/landing/button";
import { track } from "@/lib/analytics";
import { opsLoginUrl } from "@/lib/site-urls";

type NavLink = { href: string; label: string; description?: string };

type NavGroup = {
  label: string;
  href?: string;
  items?: readonly NavLink[];
};

const navGroups: readonly NavGroup[] = [
  {
    label: "Product",
    items: [
      {
        href: "/ai-voice-agents",
        label: "AI Voice Agents",
        description: "Platform for inbound voice automation",
      },
      {
        href: "/ai-receptionist",
        label: "AI Receptionist",
        description: "Answer, book, qualify, and transfer",
      },
      {
        href: "/#features",
        label: "Features",
        description: "Reception, support, sales, booking, handoff",
      },
    ],
  },
  {
    label: "Industries",
    href: "/industries",
    items: [
      { href: "/industries/home-services", label: "Home Services" },
      { href: "/industries/healthcare", label: "Healthcare" },
      { href: "/industries/legal", label: "Legal" },
      { href: "/industries/real-estate", label: "Real Estate" },
      { href: "/industries/restaurants", label: "Restaurants" },
      { href: "/industries", label: "All industries" },
    ],
  },
  {
    label: "Use Cases",
    items: [
      { href: "/use-cases/appointment-booking", label: "Appointment Booking" },
      { href: "/use-cases/lead-qualification", label: "Lead Qualification" },
      { href: "/use-cases/customer-support", label: "Customer Support" },
      { href: "/use-cases/call-answering", label: "Call Answering" },
      { href: "/use-cases/sales-calls", label: "Sales Calls" },
      { href: "/use-cases", label: "All use cases" },
    ],
  },
  { label: "Pricing", href: "/pricing" },
  { label: "Resources", href: "/blog" },
] as const;

type NavbarProps = {
  brand: string;
};

export function Navbar({ brand }: NavbarProps) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const panelId = useId();
  const navRef = useRef<HTMLElement | null>(null);
  const solid = scrolled;

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

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!navRef.current?.contains(event.target as Node)) {
        setOpenGroup(null);
      }
    };
    window.addEventListener("mousedown", onPointerDown);
    return () => window.removeEventListener("mousedown", onPointerDown);
  }, []);

  const linkTone = solid
    ? "text-muted hover:bg-bg hover:text-ink"
    : "text-hero-muted hover:bg-white/5 hover:text-white";

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 transition-[background-color,border-color,backdrop-filter,box-shadow] duration-300 ${
        solid
          ? "border-b border-line bg-surface/90 shadow-[var(--shadow-sm)] backdrop-blur-md"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <div className="content-width flex items-center justify-between gap-4 px-6 py-4 sm:px-10 lg:px-12">
        <BrandLogo
          variant={solid ? "dark" : "light"}
          priority
          className={!solid ? "brightness-100" : undefined}
        />
        <span className="sr-only">{brand}</span>

        <nav
          ref={navRef}
          className="hidden items-center gap-1 lg:flex"
          aria-label="Primary"
        >
          {navGroups.map((group) => {
            if (!group.items) {
              return (
                <Link
                  key={group.label}
                  href={group.href || "/"}
                  onClick={() =>
                    track("nav_click", { target: group.href || group.label })
                  }
                  className={`rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors ${linkTone}`}
                >
                  {group.label}
                </Link>
              );
            }

            const expanded = openGroup === group.label;
            return (
              <div key={group.label} className="relative">
                <button
                  type="button"
                  className={`inline-flex items-center gap-1 rounded-[var(--radius-sm)] px-3 py-2 text-sm font-medium transition-colors ${linkTone}`}
                  aria-expanded={expanded}
                  onClick={() =>
                    setOpenGroup((current) =>
                      current === group.label ? null : group.label,
                    )
                  }
                  onMouseEnter={() => setOpenGroup(group.label)}
                >
                  {group.label}
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                    <path
                      d="M3 4.5L6 7.5 9 4.5"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                {expanded ? (
                  <div
                    className="absolute left-0 top-full z-50 mt-2 min-w-[16rem] rounded-[var(--radius-lg)] border border-line bg-surface p-2 shadow-[var(--shadow-md)]"
                    onMouseLeave={() => setOpenGroup(null)}
                  >
                    {group.href ? (
                      <Link
                        href={group.href}
                        className="mb-1 block rounded-[var(--radius-sm)] px-3 py-2 text-xs font-semibold tracking-[0.08em] text-teal uppercase"
                        onClick={() => {
                          track("nav_click", { target: group.href! });
                          setOpenGroup(null);
                        }}
                      >
                        Overview
                      </Link>
                    ) : null}
                    <ul className="m-0 list-none p-0">
                      {group.items.map((item) => (
                        <li key={item.href}>
                          <Link
                            href={item.href}
                            className="block rounded-[var(--radius-sm)] px-3 py-2.5 transition-colors hover:bg-bg"
                            onClick={() => {
                              track("nav_click", { target: item.href });
                              setOpenGroup(null);
                            }}
                          >
                            <span className="block text-sm font-medium text-ink">
                              {item.label}
                            </span>
                            {item.description ? (
                              <span className="mt-0.5 block text-xs text-muted">
                                {item.description}
                              </span>
                            ) : null}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            );
          })}
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
          <Button
            href="/signup"
            variant={solid ? "primary" : "inverse"}
            size="md"
            className="tracking-[-0.01em]"
            onClick={() => track("cta_start_trial", { source: "nav" })}
          >
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
          className="max-h-[80vh] overflow-y-auto border-t border-line bg-surface px-6 py-4 shadow-[var(--shadow-md)] lg:hidden"
        >
          <nav aria-label="Mobile">
            <ul className="m-0 flex list-none flex-col gap-1 p-0">
              {navGroups.map((group) => (
                <li key={group.label} className="border-b border-line py-2 last:border-b-0">
                  {group.href && !group.items ? (
                    <Link
                      href={group.href}
                      className="block rounded-[var(--radius-sm)] px-3 py-3 text-sm font-medium text-ink hover:bg-bg"
                      onClick={() => {
                        track("nav_click", { target: group.href! });
                        setOpen(false);
                      }}
                    >
                      {group.label}
                    </Link>
                  ) : (
                    <>
                      <p className="m-0 px-3 py-2 text-xs font-semibold tracking-[0.12em] text-teal uppercase">
                        {group.label}
                      </p>
                      <ul className="m-0 list-none p-0">
                        {(group.items || []).map((item) => (
                          <li key={item.href}>
                            <Link
                              href={item.href}
                              className="block rounded-[var(--radius-sm)] px-3 py-2.5 text-sm text-ink-soft hover:bg-bg"
                              onClick={() => {
                                track("nav_click", { target: item.href });
                                setOpen(false);
                              }}
                            >
                              {item.label}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </li>
              ))}
              <li className="mt-2 grid gap-2 border-t border-line pt-4">
                <Button href={opsLoginUrl()} variant="secondary" className="w-full">
                  Sign in
                </Button>
                <Button
                  href="/signup"
                  variant="primary"
                  className="w-full"
                  onClick={() => track("cta_start_trial", { source: "nav_mobile" })}
                >
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

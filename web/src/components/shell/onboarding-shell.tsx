"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { OpsUser } from "@/lib/api";
import { logout } from "@/lib/api";
import { Button } from "@/components/ui";

/** Minimal chrome for mandatory onboarding — no dashboard nav. */
export function OnboardingShell({
  user,
  children,
}: {
  user: OpsUser;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-6 py-4 sm:px-8">
          <Link href="/onboarding" className="inline-flex items-center no-underline">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/branding/logo-light.svg"
              alt="Call & Flow"
              width={148}
              height={26}
              className="h-6 w-auto"
            />
          </Link>
          <div className="flex items-center gap-3 text-sm text-text-secondary">
            <span className="hidden sm:inline truncate max-w-[12rem]">
              {user.tenant_name || user.email}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                void logout().finally(() => {
                  window.location.href = "/login";
                });
              }}
            >
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl px-6 py-8 sm:px-8">{children}</main>
    </div>
  );
}

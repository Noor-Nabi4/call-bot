"use client";

import { Bot, ClipboardList } from "lucide-react";
import { Button, Surface } from "@/components/ui";

export function OnboardingChoice({
  busy,
  onChooseAi,
  onChooseManual,
}: {
  busy?: boolean;
  onChooseAi: () => void;
  onChooseManual: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="max-w-2xl">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink sm:text-3xl">
          How would you like to set up your business?
        </h1>
        <p className="mt-2 text-sm text-text-secondary sm:text-base">
          Choose AI-assisted setup or configure everything yourself. You can
          finish required details before accessing the dashboard.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Surface className="flex flex-col gap-4 p-6">
          <div className="inline-flex size-11 items-center justify-center rounded-[12px] bg-teal-soft text-teal">
            <Bot className="size-5" aria-hidden />
          </div>
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-ink">
              Set Up My Business with AI
            </h2>
            <p className="text-sm text-text-secondary">
              Describe your business in your own words. AI will prepare your
              business setup for you to review.
            </p>
          </div>
          <Button
            type="button"
            className="mt-auto w-full sm:w-auto"
            disabled={busy}
            onClick={onChooseAi}
          >
            Start with AI
          </Button>
        </Surface>

        <Surface className="flex flex-col gap-4 p-6">
          <div className="inline-flex size-11 items-center justify-center rounded-[12px] bg-surface-muted text-ink">
            <ClipboardList className="size-5" aria-hidden />
          </div>
          <div className="space-y-2">
            <h2 className="text-lg font-semibold text-ink">Set Up Manually</h2>
            <p className="text-sm text-text-secondary">
              Configure your business details, services, and preferences
              yourself.
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            className="mt-auto w-full sm:w-auto"
            disabled={busy}
            onClick={onChooseManual}
          >
            Set Up Manually
          </Button>
        </Surface>
      </div>
    </div>
  );
}

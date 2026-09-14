"use client";

import { Suspense } from "react";
import PlaygroundPage from "./playground-client";
import { LoadingSkeleton } from "@/components/ui";

export default function PlaygroundRoute() {
  return (
    <Suspense
      fallback={
        <div className="p-6">
          <LoadingSkeleton rows={8} />
        </div>
      }
    >
      <PlaygroundPage />
    </Suspense>
  );
}

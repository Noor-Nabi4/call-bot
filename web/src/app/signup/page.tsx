import { Suspense } from "react";
import SignupForm from "./signup-form";

export default function SignupRoute() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-[100svh] items-center justify-center bg-bg text-muted">
          <p className="m-0 text-sm">Loading…</p>
        </main>
      }
    >
      <SignupForm />
    </Suspense>
  );
}

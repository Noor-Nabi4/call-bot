import { Suspense } from "react";
import SignupForm from "./signup-form";

export default function SignupRoute() {
  return (
    <Suspense
      fallback={
        <main className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-ink text-[#afc2ba]">
          <div className="hero-stage" aria-hidden="true" />
          <p className="relative z-[1] m-0 text-sm">Loading…</p>
        </main>
      }
    >
      <SignupForm />
    </Suspense>
  );
}

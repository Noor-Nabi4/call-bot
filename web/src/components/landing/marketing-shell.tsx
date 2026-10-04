import type { ReactNode } from "react";
import { Footer } from "@/components/landing/footer";
import { Navbar } from "@/components/landing/navbar";
import { site } from "@/lib/copy";

type MarketingShellProps = {
  children: ReactNode;
};

export function MarketingShell({ children }: MarketingShellProps) {
  return (
    <main id="main-content">
      <Navbar brand={site.brand} />
      {children}
      <Footer />
    </main>
  );
}

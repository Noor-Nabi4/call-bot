import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in — Call & Flow",
  description: "Sign in to your Call & Flow operations console.",
  robots: { index: false, follow: false },
};

export default function LoginLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return children;
}

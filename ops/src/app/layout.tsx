import type { Metadata } from "next";
import { Fraunces, JetBrains_Mono, Manrope } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

const sans = Manrope({
  subsets: ["latin"],
  variable: "--font-ops-sans",
  display: "swap",
});

const heading = Fraunces({
  subsets: ["latin"],
  variable: "--font-ops-heading",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-ops-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Call Bot — Operations",
  description:
    "Manage calls, appointments, and field jobs for your service business.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${sans.variable} ${heading.variable} ${mono.variable} antialiased`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

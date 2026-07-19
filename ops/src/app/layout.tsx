import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Space_Grotesk } from "next/font/google";
import { Providers } from "@/components/providers";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-ops-sans",
});

const heading = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-ops-heading",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-ops-mono",
});

export const metadata: Metadata = {
  title: "Call Bot Ops",
  description: "Dispatch board and technician jobs",
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

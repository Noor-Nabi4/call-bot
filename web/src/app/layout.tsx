import type { Metadata } from "next";
import { Fraunces, Manrope } from "next/font/google";
import { buildJsonLd, buildRootMetadata } from "@/lib/metadata";
import "./globals.css";

const display = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const sans = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = buildRootMetadata();

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const jsonLd = buildJsonLd();

  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className={`${display.variable} ${sans.variable} antialiased`}>
        <a href="#main-content" className="sr-only">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}

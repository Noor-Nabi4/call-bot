import type { Metadata } from "next";
import { features, howItWorks, industries } from "@/lib/copy";
import { getSiteUrl, seo } from "@/lib/seo";

export function buildRootMetadata(): Metadata {
  const siteUrl = getSiteUrl();

  return {
    metadataBase: new URL(siteUrl),
    title: {
      default: seo.title,
      template: seo.titleTemplate,
    },
    description: seo.description,
    applicationName: seo.brand,
    authors: [{ name: seo.brand }],
    creator: seo.brand,
    publisher: seo.brand,
    keywords: [...seo.keywords],
    category: "business",
    classification: "Voice AI, Business Communications, Call Center Software",
    referrer: "origin-when-cross-origin",
    formatDetection: {
      email: false,
      address: false,
      telephone: false,
    },
    alternates: {
      canonical: "/",
    },
    openGraph: {
      type: "website",
      locale: seo.locale,
      url: siteUrl,
      siteName: seo.brand,
      title: seo.title,
      description: seo.description,
      images: [
        {
          url: "/opengraph-image",
          width: 1200,
          height: 630,
          alt: seo.ogImageAlt,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: seo.title,
      description: seo.description,
      images: ["/twitter-image"],
      ...(seo.twitterHandle
        ? { creator: seo.twitterHandle, site: seo.twitterHandle }
        : {}),
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        "max-image-preview": "large",
        "max-snippet": -1,
        "max-video-preview": -1,
      },
    },
    icons: {
      icon: [
        { url: "/favicon.ico", sizes: "any" },
        { url: "/branding/favicon.svg", type: "image/svg+xml" },
        { url: "/branding/favicon-32.png", sizes: "32x32", type: "image/png" },
        { url: "/branding/icon.png", sizes: "512x512", type: "image/png" },
      ],
      apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
    },
    manifest: "/manifest.webmanifest",
  };
}

export function buildJsonLd() {
  const siteUrl = getSiteUrl();

  const organization = {
    "@type": "Organization",
    "@id": `${siteUrl}/#organization`,
    name: seo.brand,
    url: siteUrl,
    logo: {
      "@type": "ImageObject",
      url: `${siteUrl}/icon`,
    },
    description: seo.description,
    knowsAbout: [
      "AI voice agents",
      "Phone answering service",
      "Appointment scheduling",
      "Call center operations",
      "Multi-tenant SaaS",
      "Industry agent marketplace",
    ],
  };

  const website = {
    "@type": "WebSite",
    "@id": `${siteUrl}/#website`,
    url: siteUrl,
    name: seo.brand,
    description: seo.description,
    publisher: { "@id": `${siteUrl}/#organization` },
    inLanguage: "en-US",
  };

  const software = {
    "@type": "SoftwareApplication",
    "@id": `${siteUrl}/#software`,
    name: seo.brand,
    applicationCategory: "BusinessApplication",
    applicationSubCategory: "AI Voice Agents & Call Center",
    operatingSystem: "Web",
    url: siteUrl,
    description: seo.description,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      description: "Browser demo available",
    },
    featureList: features.items.map((item) => item.title),
    audience: {
      "@type": "Audience",
      audienceType: "Service businesses and call centers",
    },
    provider: { "@id": `${siteUrl}/#organization` },
  };

  const howTo = {
    "@type": "HowTo",
    "@id": `${siteUrl}/#howto`,
    name: howItWorks.title,
    description: howItWorks.supporting,
    step: howItWorks.steps.map((step, index) => ({
      "@type": "HowToStep",
      position: index + 1,
      name: step.title,
      text: step.body,
    })),
  };

  const industryList = {
    "@type": "ItemList",
    "@id": `${siteUrl}/#industries`,
    name: industries.title,
    description: industries.supporting,
    itemListElement: industries.items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      description: item.body,
    })),
  };

  const webpage = {
    "@type": "WebPage",
    "@id": `${siteUrl}/#webpage`,
    url: siteUrl,
    name: seo.title,
    description: seo.description,
    isPartOf: { "@id": `${siteUrl}/#website` },
    about: { "@id": `${siteUrl}/#software` },
    primaryImageOfPage: {
      "@type": "ImageObject",
      url: `${siteUrl}/opengraph-image`,
    },
    speakable: {
      "@type": "SpeakableSpecification",
      cssSelector: ["#hero-heading", "#demo-heading", "#features-heading"],
    },
    inLanguage: "en-US",
  };

  return {
    "@context": "https://schema.org",
    "@graph": [
      organization,
      website,
      software,
      howTo,
      industryList,
      webpage,
    ],
  };
}

export function buildFaqJsonLd(
  items: readonly { question: string; answer: string }[],
) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}

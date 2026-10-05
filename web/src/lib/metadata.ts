import type { Metadata } from "next";
import { features, howItWorks, industries } from "@/lib/copy";
import {
  absoluteUrl,
  getSiteUrl,
  ogImagePath,
  seo,
  twitterImagePath,
} from "@/lib/seo";

export type PageMetadataInput = {
  title: string;
  description: string;
  path: string;
  /** When true, omit template and use title as-is (homepage). */
  absoluteTitle?: boolean;
  keywords?: readonly string[];
  ogType?: "website" | "article";
  noIndex?: boolean;
};

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
          url: ogImagePath(),
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
      images: [twitterImagePath()],
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

/** Unique metadata for every indexable marketing page. */
export function buildPageMetadata(input: PageMetadataInput): Metadata {
  const url = absoluteUrl(input.path);
  const fullTitle = input.absoluteTitle
    ? input.title
    : input.title.includes(`| ${seo.brand}`)
      ? input.title
      : `${input.title} | ${seo.brand}`;

  return {
    title: input.absoluteTitle
      ? { absolute: input.title }
      : input.title.includes(`| ${seo.brand}`)
        ? { absolute: input.title }
        : input.title,
    description: input.description,
    keywords: input.keywords ? [...input.keywords] : undefined,
    alternates: {
      canonical: input.path,
    },
    openGraph: {
      type: input.ogType ?? "website",
      locale: seo.locale,
      url,
      siteName: seo.brand,
      title: fullTitle,
      description: input.description,
      images: [
        {
          url: ogImagePath(),
          width: 1200,
          height: 630,
          alt: seo.ogImageAlt,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description: input.description,
      images: [twitterImagePath()],
    },
    robots: input.noIndex
      ? { index: false, follow: false }
      : {
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
  };
}

/** Sitewide schemas safe to include on every public HTML response. */
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
      "AI receptionist",
      "Phone answering service",
      "Appointment scheduling",
      "Call center operations",
      "Business phone automation",
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
      description: "Browser demo and free trial available",
    },
    featureList: features.items.map((item) => item.title),
    audience: {
      "@type": "Audience",
      audienceType: "Service businesses and call centers",
    },
    provider: { "@id": `${siteUrl}/#organization` },
  };

  return {
    "@context": "https://schema.org",
    "@graph": [organization, website, software],
  };
}

/** Homepage-only structured data (HowTo, industry list, WebPage). */
export function buildHomePageJsonLd() {
  const siteUrl = getSiteUrl();

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
      ...(item.href ? { url: absoluteUrl(item.href) } : {}),
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
      url: absoluteUrl(ogImagePath()),
    },
    speakable: {
      "@type": "SpeakableSpecification",
      cssSelector: ["#hero-heading", "#demo-heading", "#features-heading"],
    },
    inLanguage: "en-US",
  };

  return {
    "@context": "https://schema.org",
    "@graph": [howTo, industryList, webpage],
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

export function buildBreadcrumbJsonLd(
  items: readonly { name: string; path: string }[],
) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

export function buildWebPageJsonLd(input: {
  path: string;
  name: string;
  description: string;
}) {
  const siteUrl = getSiteUrl();
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${absoluteUrl(input.path)}#webpage`,
    url: absoluteUrl(input.path),
    name: input.name,
    description: input.description,
    isPartOf: { "@id": `${siteUrl}/#website` },
    about: { "@id": `${siteUrl}/#software` },
    inLanguage: "en-US",
  };
}

export function buildProductOfferJsonLd(input: {
  name: string;
  description: string;
  path: string;
  offers: readonly {
    name: string;
    price?: number | null;
    priceCurrency?: string;
    description?: string;
  }[];
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: input.name,
    description: input.description,
    brand: {
      "@type": "Brand",
      name: seo.brand,
    },
    url: absoluteUrl(input.path),
    offers: input.offers.map((offer) => ({
      "@type": "Offer",
      name: offer.name,
      ...(offer.price != null
        ? {
            price: (offer.price / 100).toFixed(2),
            priceCurrency: (offer.priceCurrency || "USD").toUpperCase(),
          }
        : {
            price: "0",
            priceCurrency: "USD",
            description: offer.description || "Contact sales for custom pricing",
          }),
      availability: "https://schema.org/InStock",
      url: absoluteUrl(input.path),
    })),
  };
}

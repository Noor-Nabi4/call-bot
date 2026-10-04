import type { MetadataRoute } from "next";
import { blogPosts } from "@/lib/marketing/blog";
import { industryPages } from "@/lib/marketing/industries";
import { PUBLIC_MARKETING_ROUTES } from "@/lib/marketing/routes";
import { useCasePages } from "@/lib/marketing/use-cases";
import { getSiteUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = getSiteUrl();
  const lastModified = new Date();

  const staticEntries: MetadataRoute.Sitemap = PUBLIC_MARKETING_ROUTES.map(
    (route) => ({
      url: route.path === "/" ? siteUrl : `${siteUrl}${route.path}`,
      lastModified,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
    }),
  );

  const industryEntries: MetadataRoute.Sitemap = industryPages.map((page) => ({
    url: `${siteUrl}/industries/${page.slug}`,
    lastModified,
    changeFrequency: "monthly",
    priority: 0.8,
  }));

  const useCaseEntries: MetadataRoute.Sitemap = useCasePages.map((page) => ({
    url: `${siteUrl}/use-cases/${page.slug}`,
    lastModified,
    changeFrequency: "monthly",
    priority: 0.8,
  }));

  const blogEntries: MetadataRoute.Sitemap = blogPosts.map((post) => ({
    url: `${siteUrl}/blog/${post.slug}`,
    lastModified: new Date(post.updatedAt),
    changeFrequency: "monthly",
    priority: 0.65,
  }));

  return [
    ...staticEntries,
    ...industryEntries,
    ...useCaseEntries,
    ...blogEntries,
  ];
}

import type { MetadataRoute } from "next";
import { seo } from "@/lib/seo";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: seo.brand,
    short_name: seo.brand,
    description: seo.description,
    start_url: "/",
    display: "standalone",
    background_color: "#FAFAFA",
    theme_color: "#0F766E",
    lang: "en-US",
    categories: ["business", "productivity"],
    icons: [
      {
        src: "/branding/pwa-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/branding/pwa-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/branding/icon.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}

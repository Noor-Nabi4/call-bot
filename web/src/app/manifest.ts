import type { MetadataRoute } from "next";
import { seo } from "@/lib/seo";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: seo.brand,
    short_name: seo.brand,
    description: seo.description,
    start_url: "/",
    display: "standalone",
    background_color: "#f3f5f7",
    theme_color: "#0e8f7d",
    lang: "en-US",
    categories: ["business", "productivity"],
    icons: [
      {
        src: "/icon",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
    ],
  };
}

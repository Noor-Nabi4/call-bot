import type { MetadataRoute } from "next";
import { seo } from "@/lib/seo";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: seo.brand,
    short_name: seo.brand,
    description: seo.description,
    start_url: "/",
    display: "standalone",
    background_color: "#f7faf8",
    theme_color: "#0f7a64",
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

import { ImageResponse } from "next/og";
import { seo } from "@/lib/seo";

export const runtime = "edge";
export const alt = seo.ogImageAlt;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function TwitterImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px",
          background:
            "linear-gradient(160deg, #07120f 0%, #0f221c 45%, #14352c 100%)",
          color: "#f3f8f5",
          fontFamily: "Georgia, serif",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: "-0.03em",
            color: "#71f0ca",
          }}
        >
          {seo.brand}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              fontSize: 64,
              fontWeight: 600,
              lineHeight: 1.05,
              letterSpacing: "-0.035em",
              maxWidth: 900,
            }}
          >
            Your AI phone team, ready in minutes.
          </div>
          <div
            style={{
              fontSize: 28,
              lineHeight: 1.35,
              color: "#afc2ba",
              maxWidth: 820,
              fontFamily: "sans-serif",
            }}
          >
            Marketplace agents, live ops, and booking — in your brand’s voice.
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}

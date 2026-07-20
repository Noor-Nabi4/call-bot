import { ImageResponse } from "next/og";
import { seo } from "@/lib/seo";

export const runtime = "edge";
export const alt = seo.ogImageAlt;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
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
          background: "linear-gradient(160deg, #0F172A 0%, #0F766E 100%)",
          color: "#FAFAFA",
          fontFamily: "Inter, system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: "-0.03em",
            color: "#14B8A6",
          }}
        >
          {seo.brand}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div
            style={{
              fontSize: 52,
              fontWeight: 600,
              lineHeight: 1.08,
              letterSpacing: "-0.035em",
              maxWidth: 920,
            }}
          >
            Build AI Voice Agents for Any Business.
          </div>
          <div
            style={{
              fontSize: 26,
              lineHeight: 1.35,
              color: "#94A3B8",
              maxWidth: 820,
            }}
          >
            AI Voice Platform for Service Businesses & Call Centers
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}

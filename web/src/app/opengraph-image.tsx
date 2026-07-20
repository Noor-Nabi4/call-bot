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
          background:
            "linear-gradient(160deg, #071416 0%, #0c2228 45%, #0a3a36 100%)",
          color: "#f3f5f7",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: "-0.03em",
            color: "#14b8a0",
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
            Answer Every Call With AI
          </div>
          <div
            style={{
              fontSize: 28,
              lineHeight: 1.35,
              color: "#9bb0b6",
              maxWidth: 820,
            }}
          >
            AI voice platform for reception, support, sales, booking, and
            handoff.
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}

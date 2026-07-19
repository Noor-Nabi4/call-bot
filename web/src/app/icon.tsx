import { ImageResponse } from "next/og";

export const runtime = "edge";
export const size = { width: 512, height: 512 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0f7a64",
          color: "#f3f8f5",
          fontSize: 220,
          fontWeight: 700,
          fontFamily: "Georgia, serif",
          letterSpacing: "-0.06em",
        }}
      >
        C
      </div>
    ),
    { ...size },
  );
}

"use client";

import Link from "next/link";

type BrandLogoProps = {
  href?: string;
  /** `light` lockup for dark surfaces; `dark` lockup for light surfaces. */
  variant?: "auto" | "light" | "dark";
  className?: string;
  priority?: boolean;
};

export function BrandLogo({
  href = "/",
  variant = "auto",
  className = "",
  priority = false,
}: BrandLogoProps) {
  const src =
    variant === "light"
      ? "/branding/logo-dark.svg"
      : variant === "dark"
        ? "/branding/logo-light.svg"
        : "/branding/logo.svg";

  const image = (
    // eslint-disable-next-line @next/next/no-img-element -- SVG brand lockups
    <img
      src={src}
      alt="Call & Flow"
      width={178}
      height={32}
      className={`h-7 w-auto sm:h-8 ${className}`}
      decoding="async"
      {...(priority ? { fetchPriority: "high" as const } : {})}
    />
  );

  if (!href) return image;

  return (
    <Link
      href={href}
      className="inline-flex items-center no-underline"
      aria-label="Call & Flow home"
    >
      {image}
    </Link>
  );
}

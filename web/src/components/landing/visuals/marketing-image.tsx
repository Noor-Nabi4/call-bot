import Image from "next/image";

type MarketingImageProps = {
  src: string;
  alt: string;
  width: number;
  height: number;
  className?: string;
  priority?: boolean;
  sizes?: string;
};

/** Optimized photo wrapper — Next.js serves WebP/AVIF when the browser allows. */
export function MarketingImage({
  src,
  alt,
  width,
  height,
  className = "",
  priority = false,
  sizes = "(max-width: 768px) 100vw, 560px",
}: MarketingImageProps) {
  return (
    <Image
      src={src}
      alt={alt}
      width={width}
      height={height}
      className={className}
      priority={priority}
      loading={priority ? "eager" : "lazy"}
      sizes={sizes}
    />
  );
}

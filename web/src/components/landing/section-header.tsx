type SectionHeaderProps = {
  eyebrow?: string;
  title: string;
  supporting?: string;
  align?: "left" | "center";
  tone?: "light" | "dark";
  id?: string;
};

export function SectionHeader({
  eyebrow,
  title,
  supporting,
  align = "left",
  tone = "light",
  id,
}: SectionHeaderProps) {
  const centered = align === "center";
  const dark = tone === "dark";

  return (
    <div className={`${centered ? "mx-auto max-w-2xl text-center" : "max-w-2xl"}`}>
      {eyebrow ? (
        <p
          className={`m-0 mb-3 inline-flex rounded-[var(--radius-sm)] px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] uppercase ${
            dark
              ? "bg-white/10 text-teal-bright"
              : "bg-teal-soft text-teal-deep"
          }`}
        >
          {eyebrow}
        </p>
      ) : null}
      <h2
        id={id}
        className={`font-display m-0 text-[clamp(1.85rem,3.8vw,2.85rem)] font-semibold leading-[1.08] tracking-[-0.04em] ${
          dark ? "text-white" : "text-ink"
        }`}
      >
        {title}
      </h2>
      {supporting ? (
        <p
          className={`mt-4 m-0 text-base leading-relaxed sm:text-lg ${
            dark ? "text-hero-muted" : "text-muted"
          } ${centered ? "mx-auto" : ""}`}
        >
          {supporting}
        </p>
      ) : null}
    </div>
  );
}

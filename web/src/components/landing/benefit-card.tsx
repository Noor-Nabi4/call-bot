type BenefitCardProps = {
  index: number;
  title: string;
  body: string;
};

export function BenefitCard({ index, title, body }: BenefitCardProps) {
  return (
    <article className="relative flex h-full flex-col gap-3 border-t border-line pt-6">
      <p className="m-0 font-mono text-xs tracking-[0.14em] text-teal uppercase">
        {String(index).padStart(2, "0")}
      </p>
      <h3 className="m-0 text-xl font-semibold tracking-[-0.02em] text-ink">
        {title}
      </h3>
      <p className="m-0 text-base leading-relaxed text-muted">{body}</p>
    </article>
  );
}

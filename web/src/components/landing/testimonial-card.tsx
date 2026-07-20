type TestimonialCardProps = {
  quote: string;
  name: string;
  role: string;
};

export function TestimonialCard({ quote, name, role }: TestimonialCardProps) {
  return (
    <figure className="card-surface card-surface-hover flex h-full flex-col gap-6 p-6 sm:p-8">
      <blockquote className="m-0 flex-1 text-base leading-relaxed text-ink-soft sm:text-[1.05rem]">
        “{quote}”
      </blockquote>
      <figcaption>
        <p className="m-0 text-sm font-semibold tracking-[-0.01em] text-ink">
          {name}
        </p>
        <p className="mt-0.5 m-0 text-sm text-muted">{role}</p>
      </figcaption>
    </figure>
  );
}

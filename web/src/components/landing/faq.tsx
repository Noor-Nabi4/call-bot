type FaqItem = {
  question: string;
  answer: string;
};

type FaqProps = {
  title: string;
  supporting: string;
  items: readonly FaqItem[];
};

export function Faq({ title, supporting, items }: FaqProps) {
  return (
    <section
      id="faq"
      className="section-pad border-t border-line bg-surface"
      aria-labelledby="faq-heading"
    >
      <div className="content-width grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16">
        <div className="max-w-md">
          <h2
            id="faq-heading"
            className="font-display m-0 text-[clamp(1.85rem,3.8vw,2.75rem)] font-semibold leading-[1.08] tracking-[-0.04em] text-ink"
          >
            {title}
          </h2>
          <p className="mt-4 m-0 text-base leading-relaxed text-muted">
            {supporting}
          </p>
        </div>
        <div className="space-y-3">
          {items.map((item) => (
            <details
              key={item.question}
              className="faq-item group rounded-[var(--radius-lg)] border border-line bg-bg px-5 py-1 open:bg-surface open:shadow-[var(--shadow-sm)]"
            >
              <summary className="flex items-center justify-between gap-4 py-4">
                <h3 className="m-0 text-base font-semibold tracking-[-0.02em] text-ink sm:text-lg">
                  {item.question}
                </h3>
                <span
                  className="faq-chevron flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-soft text-teal"
                  aria-hidden="true"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <path
                      d="M3 5l4 4 4-4"
                      stroke="currentColor"
                      strokeWidth="1.75"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              </summary>
              <p className="m-0 pb-5 text-base leading-relaxed text-muted">
                {item.answer}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

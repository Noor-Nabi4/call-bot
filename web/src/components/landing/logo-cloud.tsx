import { Reveal } from "@/components/landing/reveal";

type LogoCloudProps = {
  title: string;
  logos: readonly string[];
};

export function LogoCloud({ title, logos }: LogoCloudProps) {
  return (
    <section
      className="border-y border-line bg-surface section-pad py-12 sm:py-14"
      aria-labelledby="trusted-heading"
    >
      <div className="content-width">
        <Reveal variant="fade">
          <p
            id="trusted-heading"
            className="m-0 text-center text-sm font-medium tracking-[-0.01em] text-muted"
          >
            {title}
          </p>
        </Reveal>
        <ul className="mt-8 m-0 flex list-none flex-wrap items-center justify-center gap-x-3 gap-y-3 p-0 sm:gap-x-4">
          {logos.map((name, index) => (
            <Reveal
              key={name}
              as="li"
              variant="scale"
              delay={(index % 4) as 0 | 1 | 2 | 3}
            >
              <span className="logo-chip inline-flex items-center rounded-full border border-line bg-bg px-4 py-2 text-sm font-semibold tracking-[-0.02em] text-ink-soft">
                {name}
              </span>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

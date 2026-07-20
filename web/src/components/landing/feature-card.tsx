import type { ReactNode } from "react";

type FeatureCardProps = {
  title: string;
  body: string;
  icon?: ReactNode;
  className?: string;
};

export function FeatureCard({ title, body, icon, className = "" }: FeatureCardProps) {
  return (
    <article
      className={`card-surface card-surface-hover flex h-full flex-col gap-3 p-6 sm:p-7 ${className}`}
    >
      {icon ? (
        <div
          className="flex h-11 w-11 items-center justify-center rounded-[var(--radius-md)] bg-teal-soft text-teal"
          aria-hidden="true"
        >
          {icon}
        </div>
      ) : null}
      <h3 className="m-0 text-lg font-semibold tracking-[-0.02em] text-ink">
        {title}
      </h3>
      <p className="m-0 text-base leading-relaxed text-muted">{body}</p>
    </article>
  );
}

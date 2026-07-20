import {
  footer as footerCopy,
  site,
} from "@/lib/copy";
import {
  resolveFooterHref,
  type FooterHrefKind,
} from "@/lib/site-urls";

type FooterLink = {
  label: string;
  href?: string;
  hrefEnv?: FooterHrefKind;
};

function linkHref(link: FooterLink): string {
  if (link.hrefEnv) return resolveFooterHref(link.hrefEnv);
  return link.href || "/";
}

export function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-line bg-ink text-white">
      <div className="content-width section-pad pb-10 pt-16">
        <div className="grid gap-12 lg:grid-cols-[1.2fr_2fr]">
          <div>
            <p className="font-display m-0 text-2xl font-semibold tracking-[-0.03em]">
              {site.brand}
            </p>
            <p className="mt-3 m-0 max-w-xs text-sm leading-relaxed text-hero-muted">
              {footerCopy.tagline}
            </p>
            <p className="mt-4 m-0 max-w-sm text-sm leading-relaxed text-muted-soft">
              {footerCopy.note}
            </p>
          </div>
          <div className="grid gap-8 sm:grid-cols-3">
            {footerCopy.columns.map((column) => (
              <div key={column.title}>
                <p className="m-0 text-xs font-semibold tracking-[0.12em] text-teal-bright uppercase">
                  {column.title}
                </p>
                <ul className="mt-4 m-0 flex list-none flex-col gap-2.5 p-0">
                  {column.links.map((link) => (
                    <li key={link.label}>
                      <a
                        href={linkHref(link as FooterLink)}
                        className="text-sm text-hero-muted transition-colors hover:text-white"
                      >
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-14 flex flex-col gap-3 border-t border-white/10 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="m-0 text-sm text-muted-soft">
            © {year} {site.brand}. All rights reserved.
          </p>
          <p className="m-0 text-sm text-muted-soft">AI Voice Platform</p>
        </div>
      </div>
    </footer>
  );
}

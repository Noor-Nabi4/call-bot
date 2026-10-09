"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useCrmConfiguration } from "@/lib/crm/use-crm-configuration";
import {
  isActivePath,
  navSectionsFor,
  sectionContainingPath,
  type NavSectionId,
} from "./nav";

const SECTION_OPEN_KEY = "ops-nav-sections-open";
const SIDEBAR_COLLAPSED_KEY = "ops-sidebar-collapsed";
const SIDEBAR_COLLAPSED_EVENT = "ops-sidebar-collapsed-change";

type OpenMap = Partial<Record<NavSectionId, boolean>>;

function readOpenMap(): OpenMap {
  try {
    const raw = localStorage.getItem(SECTION_OPEN_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as OpenMap;
  } catch {
    return {};
  }
}

function writeOpenMap(map: OpenMap) {
  try {
    localStorage.setItem(SECTION_OPEN_KEY, JSON.stringify(map));
  } catch {
    /* ignore */
  }
}

function expandSidebar() {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, "0");
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(SIDEBAR_COLLAPSED_EVENT));
}

export function SidebarNavigation({
  user,
  collapsed,
}: {
  user: OpsUser;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  const { config } = useCrmConfiguration(user);
  const sections = useMemo(
    () => navSectionsFor(user, config?.navigation),
    [user, config?.navigation],
  );
  const [openMap, setOpenMap] = useState<OpenMap>({});

  useEffect(() => {
    setOpenMap(readOpenMap());
  }, []);

  // Active route auto-expands its parent section.
  useEffect(() => {
    const activeId = sectionContainingPath(sections, pathname);
    if (!activeId) return;
    setOpenMap((prev) => {
      if (prev[activeId]) return prev;
      const next = { ...prev, [activeId]: true };
      writeOpenMap(next);
      return next;
    });
  }, [pathname, sections]);

  function isSectionOpen(id: NavSectionId): boolean {
    if (openMap[id] === undefined) return true;
    return Boolean(openMap[id]);
  }

  function toggleSection(id: NavSectionId) {
    setOpenMap((prev) => {
      const currently = prev[id] === undefined ? true : Boolean(prev[id]);
      const next = { ...prev, [id]: !currently };
      writeOpenMap(next);
      return next;
    });
  }

  if (!sections.length) {
    return (
      <nav aria-label="Primary" className="flex flex-1 flex-col px-2 py-3" />
    );
  }

  // Collapsed rail: section icons only (permission-filtered sections).
  if (collapsed) {
    return (
      <nav
        aria-label="Primary"
        className="flex flex-1 flex-col items-center gap-1 overflow-y-auto px-1.5 py-3"
      >
        {sections.map((section) => {
          const Icon = section.icon;
          const active =
            sectionContainingPath([section], pathname) === section.id;
          const first = section.items[0];
          return (
            <Link
              key={section.id}
              href={first?.href || "/dashboard"}
              title={section.label}
              onClick={() => {
                expandSidebar();
                setOpenMap((prev) => {
                  const next = { ...prev, [section.id]: true };
                  writeOpenMap(next);
                  return next;
                });
              }}
              className={cn(
                "inline-flex size-10 items-center justify-center rounded-[10px] transition-all duration-200",
                active
                  ? "bg-teal-bright/18 text-white shadow-[inset_0_0_0_1px_rgba(20,184,160,0.28)]"
                  : "text-hero-muted hover:bg-white/10 hover:text-white",
              )}
              aria-label={section.label}
            >
              <Icon
                className={cn(
                  "size-4",
                  active ? "text-teal-bright" : "text-current",
                )}
                aria-hidden
              />
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <nav
      aria-label="Primary"
      className="flex flex-1 flex-col gap-2 overflow-y-auto px-2 py-3"
    >
      {sections.map((section) => {
        const open = isSectionOpen(section.id);
        const SectionIcon = section.icon;
        return (
          <div key={section.id} className="flex flex-col gap-0.5">
            <button
              type="button"
              onClick={() => toggleSection(section.id)}
              className="flex w-full items-center gap-2 rounded-[10px] px-3 py-1.5 text-left text-[10px] font-semibold tracking-[0.16em] text-hero-muted/80 uppercase transition-colors hover:bg-white/5 hover:text-hero-muted"
              aria-expanded={open}
              aria-controls={`nav-section-${section.id}`}
            >
              <SectionIcon className="size-3.5 shrink-0 opacity-80" aria-hidden />
              <span className="flex-1">{section.label}</span>
              {open ? (
                <ChevronDown className="size-3.5 opacity-70" aria-hidden />
              ) : (
                <ChevronRight className="size-3.5 opacity-70" aria-hidden />
              )}
            </button>
            {open ? (
              <div
                id={`nav-section-${section.id}`}
                className="flex flex-col gap-0.5"
              >
                {section.items.map((item) => {
                  const active = isActivePath(pathname, item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={item.label}
                      className={cn(
                        "ops-nav-item inline-flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-sm font-medium transition-all duration-200",
                        active
                          ? "bg-teal-bright/18 text-white shadow-[inset_0_0_0_1px_rgba(20,184,160,0.28)]"
                          : "text-hero-muted hover:bg-white/10 hover:text-white",
                      )}
                      aria-current={active ? "page" : undefined}
                    >
                      <Icon
                        className={cn(
                          "size-4 shrink-0 transition-transform duration-200",
                          active ? "text-teal-bright scale-105" : "text-current",
                        )}
                        aria-hidden
                      />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </nav>
  );
}

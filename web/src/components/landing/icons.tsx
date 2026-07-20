/** Lightweight inline icons for feature cards — original, not from Figma. */

import type { ReactNode } from "react";

type IconProps = {
  className?: string;
};

function frame({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 22 22"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function IconWave({ className }: IconProps) {
  return frame({
    className,
    children: (
      <path
        d="M2 11c2-4 4-4 6 0s4 4 6 0 4-4 6 0"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    ),
  });
}

export function IconCalendar({ className }: IconProps) {
  return frame({
    className,
    children: (
      <>
        <rect
          x="3"
          y="5"
          width="16"
          height="14"
          rx="2"
          stroke="currentColor"
          strokeWidth="1.75"
        />
        <path
          d="M3 9h16M8 3v4M14 3v4"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      </>
    ),
  });
}

export function IconBook({ className }: IconProps) {
  return frame({
    className,
    children: (
      <path
        d="M4 5.5A2.5 2.5 0 016.5 3H18v14H6.5A2.5 2.5 0 004 19.5V5.5z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    ),
  });
}

export function IconHandoff({ className }: IconProps) {
  return frame({
    className,
    children: (
      <path
        d="M7 14a3 3 0 100-6 3 3 0 000 6zM15 14a3 3 0 100-6 3 3 0 000 6zM10 11h2"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    ),
  });
}

export function IconLayers({ className }: IconProps) {
  return frame({
    className,
    children: (
      <path
        d="M11 3l8 4-8 4-8-4 8-4zM3 11l8 4 8-4M3 15l8 4 8-4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    ),
  });
}

export function IconChart({ className }: IconProps) {
  return frame({
    className,
    children: (
      <path
        d="M4 17V9M11 17V5M18 17v-6"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    ),
  });
}

"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { ArrowUpRightIcon } from "@/components/landing/icons";
import { Magnetic } from "@/components/landing/Magnetic";
import { cn } from "@/lib/utils";

type Tone = "dark" | "light" | "glass" | "alert";

type CtaProps = {
  href: string;
  children: ReactNode;
  tone?: Tone;
  arrow?: boolean;
  magnetic?: boolean;
  shape?: "rounded" | "pill";
  className?: string;
  onClick?: () => void;
  ariaLabel?: string;
};

const TONES: Record<Tone, { button: string; badge: string }> = {
  dark: {
    button: "bg-ink text-white hover:bg-ink-soft shadow-[0_4px_14px_rgba(8,11,15,0.18)]",
    badge: "bg-white text-ink",
  },
  light: {
    button: "bg-white text-ink hover:bg-surface shadow-[0_4px_14px_rgba(0,0,0,0.08)]",
    badge: "bg-ink text-white",
  },
  glass: {
    button: "border border-white/30 bg-white/10 text-white backdrop-blur-md hover:border-white/60 hover:bg-white/20",
    badge: "bg-white text-ink",
  },
  alert: {
    button: "bg-[#c62828] text-white hover:bg-[#b71c1c] shadow-[0_4px_16px_rgba(198,40,40,0.35)]",
    badge: "bg-white text-[#c62828]",
  },
};

export function Cta({
  href,
  children,
  tone = "dark",
  arrow = false,
  magnetic = false,
  shape = "rounded",
  className,
  onClick,
  ariaLabel,
}: CtaProps) {
  const t = TONES[tone];
  const isHash = href.startsWith("#");

  const classes = cn(
    "group press inline-flex h-11 items-center gap-3 text-caption font-semibold whitespace-nowrap",
    shape === "pill" ? "rounded-full" : "rounded-md",
    "transition-[background-color,border-color,color,transform,box-shadow] duration-300 ease-site",
    arrow ? (shape === "pill" ? "py-2 pr-2 pl-5" : "py-2 pr-2 pl-4") : "px-5",
    t.button,
    !magnetic && className,
  );

  const innerContent = (
    <>
      <span>{children}</span>
      {arrow && (
        <span className={cn("grid size-7 shrink-0 place-items-center rounded-full transition-transform duration-300", t.badge)}>
          <ArrowUpRightIcon className="arrow-badge size-3.5" />
        </span>
      )}
    </>
  );

  const element = isHash ? (
    <a href={href} onClick={onClick} aria-label={ariaLabel} className={classes}>
      {innerContent}
    </a>
  ) : (
    <Link href={href} onClick={onClick} aria-label={ariaLabel} className={classes}>
      {innerContent}
    </Link>
  );

  return magnetic ? <Magnetic className={className}>{element}</Magnetic> : element;
}

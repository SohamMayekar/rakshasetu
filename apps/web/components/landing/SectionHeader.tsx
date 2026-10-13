import type { ReactNode } from "react";

import { SectionTag } from "@/components/landing/SectionTag";
import { cn } from "@/lib/utils";

type Layout = "centred" | "row" | "stack";

type SectionHeaderProps = {
  tag: string;
  heading: string;
  body?: string;
  aside?: ReactNode;
  layout?: Layout;
  tone?: "dark" | "light";
  className?: string;
  headingId?: string;
};

export function SectionHeader({
  tag,
  heading,
  body,
  aside,
  layout,
  tone = "dark",
  className,
  headingId,
}: SectionHeaderProps) {
  const dark = tone === "dark";
  const mode: Layout = layout ?? (aside ? "row" : "centred");
  const centred = mode === "centred";

  const unit = (
    <div className={cn(centred ? "mx-auto flex max-w-[56rem] flex-col items-center text-center" : "max-w-[52rem]")}>
      <div data-reveal="">
        <SectionTag tone={dark ? "dark" : "light"}>{tag}</SectionTag>
      </div>
      <h2
        id={headingId}
        data-reveal=""
        className={cn(
          "mt-5 text-balance font-display text-display-lg font-bold tracking-[-0.035em]",
          centred && "max-w-[28ch]",
          dark ? "text-ink" : "text-white",
        )}
      >
        {heading}
      </h2>
      {body && (
        <p
          data-reveal=""
          className={cn(
            "mt-4 max-w-[44rem] text-pretty text-body-lg",
            dark ? "text-slate" : "text-white/80",
          )}
        >
          {body}
        </p>
      )}
    </div>
  );

  if (mode === "stack") return <div className={className}>{unit}</div>;

  return (
    <div
      className={cn(
        "header-gap",
        aside && "flex flex-col gap-6 md:flex-row md:items-end md:justify-between md:gap-10",
        className,
      )}
    >
      {unit}
      {aside && (
        <div data-reveal="" className="shrink-0">
          {aside}
        </div>
      )}
    </div>
  );
}

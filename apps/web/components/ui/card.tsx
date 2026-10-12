// Surfaces (m60): white cards on the canvas, round icon wells, and the page heading every desk-side screen
// opens with. Neutral only: hue stays reserved for priority.

import type { LucideIcon } from "lucide-react";
import type { ElementType, ReactNode } from "react";

export function Card({ as: As = "div", className = "", children, ...rest }: {
  as?: ElementType; className?: string; children: ReactNode; [k: string]: unknown;
}) {
  return <As {...rest} className={`rounded-card border border-line/80 bg-paper shadow-[var(--shadow-card)] ${className}`}>{children}</As>;
}

export function IconWell({ icon: Icon, size = "md", tone = "wash", label }: {
  icon: LucideIcon; size?: "sm" | "md" | "lg"; tone?: "wash" | "ink" | "paper"; label?: string;
}) {
  const s = { sm: "size-8 [&>svg]:size-4", md: "size-10 [&>svg]:size-[18px]", lg: "size-12 [&>svg]:size-5" }[size];
  const t = { wash: "bg-wash text-ink", ink: "bg-ink text-paper", paper: "bg-paper text-ink border border-line" }[tone];
  return (
    <span className={`grid shrink-0 place-items-center rounded-full ${s} ${t}`} aria-hidden={label ? undefined : true} aria-label={label} title={label}>
      <Icon strokeWidth={1.8} />
    </span>
  );
}

export function PageHeader({ title, sub, aside }: { title: ReactNode; sub?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-display font-semibold leading-tight tracking-tight">{title}</h1>
        {sub && <p className="mt-1 text-body text-ink-2">{sub}</p>}
      </div>
      {aside && <div className="flex items-center gap-2">{aside}</div>}
    </header>
  );
}

// A quiet pill for "where/when" facts in a header (today's date, a filter), like a label you can't miss.
export function Pill({ icon: Icon, children, title }: { icon?: LucideIcon; children: ReactNode; title?: string }) {
  return (
    <span title={title} className="inline-flex h-9 items-center gap-2 rounded-full bg-paper px-3.5 text-body text-ink-2 shadow-[var(--shadow-card)]">
      {Icon && <Icon className="size-4 text-ink-3" strokeWidth={1.8} aria-hidden />}
      {children}
    </span>
  );
}

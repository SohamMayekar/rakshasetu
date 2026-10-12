// Small text primitives: section headers in the PS's words, "because" lines, estimates, relative times.

"use client";

import type { LucideIcon } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

export function Section({ title, icon: Icon, aside, children }: { title: string; icon?: LucideIcon; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="border-t border-line py-5 first:border-t-0">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-body font-semibold tracking-tight">
          {Icon && <Icon className="size-4 text-ink-3" strokeWidth={1.9} aria-hidden />}{title}
        </h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

// Every decision shows its because (PRD §13.5 #6).
export function Because({ children }: { children: ReactNode }) {
  return <p className="text-xs leading-snug text-ink-2"><span className="text-ink-3">because </span>{children}</p>;
}

export function Estimate({ value, kind }: { value: number | null | undefined; kind?: string | null }) {
  if (value == null) return <span className="text-ink-3">?</span>;
  return <span className="tabular" title={kind === "estimated" ? "An estimate" : undefined}>{kind === "estimated" ? "~" : ""}{value}</span>;
}

export function ago(iso: string | null | undefined, now: number): string {
  if (!iso) return "";
  const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h} h ${m % 60} min ago` : `${Math.floor(h / 24)} d ago`;
}

export function useNow(everyMs = 15000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), everyMs); return () => clearInterval(t); }, [everyMs]);
  return now;
}

// A relative time that fades once it is older than `staleAfterMin` (staleness is fade, §13.5).
export function Ago({ iso, staleAfterMin }: { iso: string | null | undefined; staleAfterMin?: number }) {
  const now = useNow();
  if (!iso) return null;
  const stale = staleAfterMin != null && now - new Date(iso).getTime() > staleAfterMin * 60000;
  const at = new Date(iso);
  return <time dateTime={iso} title={at.toLocaleString("en-IN")} className={`tabular ${stale ? "stale" : ""}`}>{ago(iso, now)}</time>;
}

export function Clock({ iso }: { iso: string | null | undefined }) {
  if (!iso) return null;
  return <time dateTime={iso} className="tabular">{new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}</time>;
}

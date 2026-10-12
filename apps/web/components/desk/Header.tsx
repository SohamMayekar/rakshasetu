"use client";

// The desk's top line: which incident, which districts, whether live updates are flowing, and today's date and
// time (a control room lives by the clock). Navigation, who you are and Sign out live in the sidebar (m60).

import { CalendarDays } from "lucide-react";

import { Clock, useNow } from "@/components/ui";
import type { Me } from "@/lib/api";
import type { LiveState } from "@/lib/live";

export function Header({ me, incident, live }: { me: Me | null; incident: string; live: LiveState }) {
  const inc = me?.incidents.find((i) => i.code === incident);
  const now = useNow(30_000);
  const districts = me?.districts.filter((d) => d.incident_id === inc?.id).map((d) => d.name) ?? [];
  return (
    <header className="flex items-start justify-between gap-4 px-1">
      <div className="min-w-0">
        <h1 className="truncate text-title font-semibold leading-tight tracking-tight">{inc ? inc.name : incident}</h1>
        <p className="text-small text-ink-2">{districts.length ? `${districts.join(" · ")} control room` : "District control room"}
          {me?.demo_mode && <span className="text-ink-3"> · demo data, clock 60× faster</span>}</p>
      </div>
      <div className="flex h-8 shrink-0 items-center gap-4 text-small text-ink-2">   {/* plain text, not more cards (m79) */}
        {live.connected ? (
          <span className="inline-flex items-center gap-1.5" title="Live updates are flowing"><span className="size-2 rounded-full bg-ink" aria-hidden />Live</span>
        ) : live.pausedSince ? (
          <span className="inline-flex h-8 items-center rounded-full bg-ink px-3 font-medium text-paper">Live updates paused since <Clock iso={live.pausedSince} /></span>
        ) : (
          <span>Connecting…</span>
        )}
        <span className="hidden items-center gap-1.5 sm:inline-flex">
          <CalendarDays className="size-4 text-ink-3" strokeWidth={1.8} aria-hidden />
          <span className="tabular">{new Date(now).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</span>
          <span className="tabular font-semibold text-ink">{new Date(now).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })}</span>
        </span>
      </div>
    </header>
  );
}

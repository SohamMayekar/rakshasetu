"use client";

// The desk's top line: where you are, who you are, and whether live updates are flowing.
// (The promise bar joins it in m47; until then no numbers are shown here rather than invented ones.)

import { Clock } from "@/components/ui";
import type { Me } from "@/lib/api";
import type { LiveState } from "@/lib/live";

export function Header({ me, incident, live }: { me: Me | null; incident: string; live: LiveState }) {
  const inc = me?.incidents.find((i) => i.code === incident);
  return (
    <header className="flex h-12 items-center justify-between border-b border-line px-4">
      <div className="flex items-baseline gap-3">
        <a href="/" className="font-semibold tracking-tight">RakshaSetu</a>
        <span className="hidden text-sm text-ink-2 sm:inline">{inc ? inc.name : incident}</span>
        <span className="hidden text-xs text-ink-3 lg:inline">{me?.districts.filter((d) => d.incident_id === inc?.id).map((d) => d.name).join(" · ")}</span>
      </div>
      <div className="flex items-center gap-4 text-sm">
        {live.connected ? (
          <span className="inline-flex items-center gap-1.5 text-ink-2"><span className="h-2 w-2 rounded-full bg-ink" aria-hidden />Live</span>
        ) : live.pausedSince ? (
          <span className="rounded-full bg-ink px-2.5 py-0.5 text-xs font-medium text-paper">Live updates paused since <Clock iso={live.pausedSince} /></span>
        ) : (
          <span className="text-ink-3">Connecting…</span>
        )}
        {me?.permissions.includes("audit.read") && <a href="/audit" className="hidden text-ink-2 hover:text-ink sm:inline">Audit</a>}
        {me && <span className="hidden text-ink-2 sm:inline">{me.user.name} <span className="text-ink-3">· {me.user.role_label}</span></span>}
        <a href="/login" onClick={() => fetch("/v1/auth/logout", { method: "POST" })} className="text-ink-3 hover:text-ink">Sign out</a>
      </div>
    </header>
  );
}

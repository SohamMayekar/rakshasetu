"use client";

// The desk's top row (m73): three numbers about families, not about the system. How many need a person now, how
// many have a rescue team on the way or on site, how many are rescued or closed. A number turns to ink with one
// short line only when lives are at risk: an urgent family with no team for 5 minutes, or a team not heard from.

import { CircleCheck, LifeBuoy, Siren } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { IconWell } from "@/components/ui";
import { api, type Promises } from "@/lib/api";
import type { Queue } from "@/lib/queue";

const plural = (n: number, one: string, many: string) => `${n.toLocaleString("en-IN")} ${n === 1 ? one : many}`;

function Tile({ icon, label, value, alert, children }: {
  icon: typeof Siren; label: string; value: number | null; alert?: boolean; children?: ReactNode;
}) {
  return (
    <div className={`flex min-w-0 items-center gap-3 px-4 py-3 ${alert ? "bg-wash" : ""}`}>
      <IconWell icon={icon} tone={alert ? "ink" : "wash"} />
      <div className="min-w-0 leading-tight">
        <p className="text-small text-ink-2">{label}</p>
        <p className="flex flex-wrap items-baseline gap-x-2">
          <span className="tabular text-title font-semibold">{value ?? "–"}</span>
          {children}
        </p>
      </div>
    </div>
  );
}

const warn = (text: string) => <span className="rounded-md bg-ink px-1.5 text-body font-medium text-paper">{text}</span>;

/** Families waiting for a person: a sheet's group row stands for each family in it. */
export const waitingFamilies = (q: Queue) => q.rows.reduce((n, r) => n + (r.kind === "group" ? r.members?.length ?? 1 : 1), 0);

export function Today({ incident, queue }: { incident: string; queue: Queue | null }) {
  const [p, setP] = useState<Promises | null>(null);   // only for the two life-at-risk warnings
  useEffect(() => {
    let alive = true;
    const load = () => api<Promises>(`/v1/metrics/promises?incident=${encodeURIComponent(incident)}`).then((x) => alive && setP(x)).catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => { alive = false; clearInterval(t); };
  }, [incident]);
  const unowned = p?.stale.p1_unowned ?? 0, quiet = p?.stale.overdue ?? 0;
  return (
    // One strip, three parts (m79): the numbers belong together, so they share one surface instead of three cards.
    <div className="grid grid-cols-1 divide-y divide-line overflow-hidden rounded-card border border-line/80 bg-paper shadow-[var(--shadow-card)] md:grid-cols-3 md:divide-x md:divide-y-0" aria-label="Today">
      <Tile icon={Siren} label="Need help now" value={queue ? waitingFamilies(queue) : null} alert={unowned > 0}>
        {unowned > 0 ? warn(`${plural(unowned, "urgent family", "urgent families")} without a team`) : <span className="text-small text-ink-2">families</span>}
      </Tile>
      <Tile icon={LifeBuoy} label="A rescue team is on it" value={queue?.on_it ?? null} alert={quiet > 0}>
        {quiet > 0 ? warn(`${plural(quiet, "team", "teams")} not heard from`) : <span className="text-small text-ink-2">families</span>}
      </Tile>
      <Tile icon={CircleCheck} label="Rescued or closed" value={queue ? queue.rescued_closing + queue.closed : null}>
        <span className="text-small text-ink-2">families</span>
      </Tile>
    </div>
  );
}

"use client";

// The promise bar (PRD F-C6): the tagline as three invariants that add up. Every number is its own database
// query (tested); a number inverts (ink chip) only when its promise is broken, never because it is large.
// Numbers that have a queue behind them filter "Needs you now" when clicked. m60: three quiet cards, each with
// its promise's icon, in a row; still words and numbers only (no charts, no trend arrows).

import { CopyCheck, Inbox, Timer } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { IconWell } from "@/components/ui";
import { api } from "@/lib/api";

export type Promises = {
  lost: { reports: number; cases: number; merged: number; to_check: number; without_home: number; oldest_waiting_s: number | null; adds_up: boolean; broken: boolean };
  doubled: { merged: number; to_check: number; refused: number; broken: boolean };
  stale: { p1_unowned: number; overdue: number; owned: number; broken: boolean };
};
export type QueueFilter = "p1_unowned" | "overdue" | "duplicates" | null;

function N({ v, broken, onClick, title }: { v: number; broken?: boolean; onClick?: () => void; title?: string }) {
  const cls = `tabular font-semibold ${broken ? "rounded-md bg-ink px-1.5 text-paper" : "text-ink"} ${onClick ? "cursor-pointer underline-offset-2 hover:underline" : ""}`;
  return onClick ? <button title={title} onClick={onClick} className={cls}>{v}</button> : <span title={title} className={cls}>{v}</span>;
}

const age = (s: number | null) => (s == null ? "" : s < 60 ? `${s} s` : `${Math.round(s / 60)} min`);

function PromiseCard({ icon, name, broken, children }: { icon: typeof Inbox; name: string; broken: boolean; children: ReactNode }) {
  return (
    <div className={`flex min-w-0 items-center gap-3 rounded-2xl bg-paper px-3.5 py-2.5 shadow-[var(--shadow-card)] ${broken ? "ring-2 ring-ink" : ""}`}>
      <IconWell icon={icon} tone={broken ? "ink" : "wash"} />
      <div className="min-w-0 leading-snug">
        <p className="text-[13px] font-semibold">{name}</p>
        <p className="text-sm leading-snug text-ink-2">{children}</p>
      </div>
    </div>
  );
}

export function PromiseBar({ incident, onFilter }: { incident: string; onFilter: (f: QueueFilter) => void }) {
  const [p, setP] = useState<Promises | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => api<Promises>(`/v1/metrics/promises?incident=${encodeURIComponent(incident)}`).then((x) => alive && setP(x)).catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => { alive = false; clearInterval(t); };
  }, [incident]);
  if (!p) return <div className="h-[62px]" />;
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-[1.55fr_1fr_1.25fr]" aria-label="Promise bar">
      <PromiseCard icon={Inbox} name="Never lost" broken={p.lost.broken}>
        <N v={p.lost.reports} /> reports = <N v={p.lost.cases} /> cases + <N v={p.lost.merged} /> merged + <N v={p.lost.to_check} /> to check
        {" "}+ <N v={p.lost.without_home} broken={p.lost.broken} title="Reports still being read; broken if one waits over 2 min" /> not yet read
        {p.lost.oldest_waiting_s != null && <span> · oldest waiting {age(p.lost.oldest_waiting_s)}</span>}
      </PromiseCard>
      <PromiseCard icon={CopyCheck} name="Never doubled" broken={p.doubled.broken}>
        <N v={p.doubled.merged} /> merged · <N v={p.doubled.to_check} broken={p.doubled.broken} onClick={() => onFilter("duplicates")}
                                                title="Maybe repeats waiting for a person; broken if one waits over 15 min" /> to check
        {" "}· <N v={p.doubled.refused} /> kept apart
      </PromiseCard>
      <PromiseCard icon={Timer} name="Never stale" broken={p.stale.broken}>
        <N v={p.stale.p1_unowned} broken={p.stale.p1_unowned > 0} onClick={() => onFilter("p1_unowned")} /> urgent without a team &gt; 5 min
        {" "}· <N v={p.stale.overdue} broken={p.stale.overdue > 0} onClick={() => onFilter("overdue")} /> contact overdue
      </PromiseCard>
    </div>
  );
}

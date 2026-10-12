"use client";

// The promise bar (PRD F-C6): the tagline as three invariants that add up. Every number is its own database
// query (tested); a number inverts (ink chip) only when its promise is broken, never because it is large.
// Numbers that have a queue behind them filter "Needs you now" when clicked.

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export type Promises = {
  lost: { reports: number; cases: number; merged: number; to_check: number; without_home: number; oldest_waiting_s: number | null; adds_up: boolean; broken: boolean };
  doubled: { merged: number; to_check: number; refused: number; broken: boolean };
  stale: { p1_unowned: number; overdue: number; owned: number; broken: boolean };
};
export type QueueFilter = "p1_unowned" | "overdue" | "duplicates" | null;

function N({ v, broken, onClick, title }: { v: number; broken?: boolean; onClick?: () => void; title?: string }) {
  const cls = `tabular font-semibold ${broken ? "rounded bg-ink px-1.5 text-paper" : ""} ${onClick ? "cursor-pointer underline-offset-2 hover:underline" : ""}`;
  return onClick ? <button title={title} onClick={onClick} className={cls}>{v}</button> : <span title={title} className={cls}>{v}</span>;
}

const age = (s: number | null) => (s == null ? "" : s < 60 ? `${s} s` : `${Math.round(s / 60)} min`);

export function PromiseBar({ incident, onFilter }: { incident: string; onFilter: (f: QueueFilter) => void }) {
  const [p, setP] = useState<Promises | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () => api<Promises>(`/v1/metrics/promises?incident=${encodeURIComponent(incident)}`).then((x) => alive && setP(x)).catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => { alive = false; clearInterval(t); };
  }, [incident]);
  if (!p) return <div className="h-11 border-b border-line" />;
  const col = "flex min-w-0 flex-col justify-center px-4";
  const head = "text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-3";
  return (
    <div className="grid grid-cols-1 border-b border-line text-sm md:grid-cols-[1.6fr_1fr_1fr]" aria-label="Promise bar">
      <div className={`${col} py-1.5`}>
        <span className={head}>Never lost · provenance</span>
        <span className="truncate">
          <N v={p.lost.reports} /> reports = <N v={p.lost.cases} /> cases + <N v={p.lost.merged} /> merged + <N v={p.lost.to_check} /> to check
          {" "}+ <N v={p.lost.without_home} broken={p.lost.broken} title="Reports still in the pipeline; broken if one waits over 2 min" /> without a home
          {p.lost.oldest_waiting_s != null && <span className="text-ink-2"> · oldest waiting {age(p.lost.oldest_waiting_s)}</span>}
        </span>
      </div>
      <div className={`${col} border-line py-1.5 md:border-l`}>
        <span className={head}>Never doubled · uncertainty</span>
        <span className="truncate">
          <N v={p.doubled.merged} /> merged · <N v={p.doubled.to_check} broken={p.doubled.broken} onClick={() => onFilter("duplicates")}
                                                  title="Likely duplicates waiting for a person; broken if one waits over 15 min" /> to check
          {" "}· <N v={p.doubled.refused} /> refused
        </span>
      </div>
      <div className={`${col} border-line py-1.5 md:border-l`}>
        <span className={head}>Never stale · responsibility</span>
        <span className="truncate">
          <N v={p.stale.p1_unowned} broken={p.stale.p1_unowned > 0} onClick={() => onFilter("p1_unowned")} /> P1 without owner &gt; 5 min
          {" "}· <N v={p.stale.overdue} broken={p.stale.overdue > 0} onClick={() => onFilter("overdue")} /> contact overdue
        </span>
      </div>
    </div>
  );
}

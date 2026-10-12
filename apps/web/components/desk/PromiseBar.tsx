"use client";

// The promise bar (PRD F-C6): the tagline as three short sentences, one per promise (m67): "Nobody lost: 343
// reports → 252 families", "No family counted twice: 91 repeats merged", "Nobody forgotten: every urgent family
// has a team". A broken promise turns its card to ink and says what broke. "Show details" opens the sums that
// prove each one (every number is its own database query, tested); the numbers with a list behind them filter
// "Needs you now" when clicked. Words and numbers only: no charts, no trend arrows.

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
        <p className="text-sm leading-snug text-ink">{children}</p>
      </div>
    </div>
  );
}

const plural = (n: number, one: string, many: string) => `${n.toLocaleString("en-IN")} ${n === 1 ? one : many}`;

// The tagline as three short sentences (m67), one per promise; the sums that prove each one are a click away.
export function PromiseBar({ incident, onFilter }: { incident: string; onFilter: (f: QueueFilter) => void }) {
  const [p, setP] = useState<Promises | null>(null);
  const [details, setDetails] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () => api<Promises>(`/v1/metrics/promises?incident=${encodeURIComponent(incident)}`).then((x) => alive && setP(x)).catch(() => {});
    load();
    const t = setInterval(load, 2000);
    return () => { alive = false; clearInterval(t); };
  }, [incident]);
  if (!p) return <div className="h-[62px]" />;
  const b = (text: string) => <b className="rounded-md bg-ink px-1.5 font-semibold text-paper">{text}</b>;
  return (
    <div aria-label="Promise bar">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
        <PromiseCard icon={Inbox} name="Never lost" broken={p.lost.broken}>
          {p.lost.broken ? b(`${plural(p.lost.without_home, "report", "reports")} not read for 2 min`)
            : `Nobody lost: ${plural(p.lost.reports, "report", "reports")} → ${plural(p.lost.cases, "family", "families")}`}
        </PromiseCard>
        <PromiseCard icon={CopyCheck} name="Never doubled" broken={p.doubled.broken}>
          {p.doubled.broken ? b(`${plural(p.doubled.to_check, "possible repeat", "possible repeats")} waiting 15 min`)
            : `No family counted twice: ${plural(p.doubled.merged, "repeat", "repeats")} merged`}
        </PromiseCard>
        <PromiseCard icon={Timer} name="Never stale" broken={p.stale.broken}>
          {p.stale.overdue > 0 ? b(`${plural(p.stale.overdue, "team", "teams")} not heard from`)
            : p.stale.p1_unowned > 0 ? b(`${plural(p.stale.p1_unowned, "urgent family", "urgent families")} without a team`)
            : "Nobody forgotten: every urgent family has a team"}
        </PromiseCard>
        <button onClick={() => setDetails(!details)} aria-expanded={details}
                className="self-center justify-self-start rounded-full px-3 py-1.5 text-[13px] text-ink-2 underline-offset-2 hover:underline">
          {details ? "Hide details" : "Show details"}
        </button>
      </div>
      {details && (
        <div className="mt-2 grid grid-cols-1 gap-1.5 rounded-2xl bg-paper px-4 py-3 text-sm text-ink-2 shadow-[var(--shadow-card)] md:grid-cols-3">
          <p><N v={p.lost.reports} /> reports = <N v={p.lost.cases} /> cases + <N v={p.lost.merged} /> merged + <N v={p.lost.to_check} /> to check
            {" "}+ <N v={p.lost.without_home} broken={p.lost.broken} title="Reports still being read; broken if one waits over 2 min" /> not yet read
            {p.lost.oldest_waiting_s != null && <span> · oldest waiting {age(p.lost.oldest_waiting_s)}</span>}</p>
          <p><N v={p.doubled.merged} /> merged · <N v={p.doubled.to_check} broken={p.doubled.broken} onClick={() => onFilter("duplicates")}
                                                      title="Maybe repeats waiting for a person; broken if one waits over 15 min" /> to check
            {" "}· <N v={p.doubled.refused} /> kept apart (different names)</p>
          <p><N v={p.stale.p1_unowned} broken={p.stale.p1_unowned > 0} onClick={() => onFilter("p1_unowned")} /> urgent without a team &gt; 5 min
            {" "}· <N v={p.stale.overdue} broken={p.stale.overdue > 0} onClick={() => onFilter("overdue")} /> contact overdue
            {" "}· <span className="text-ink-3">click a number to list them</span></p>
        </div>
      )}
    </div>
  );
}

"use client";

// Escalations for this desk's role, above the queue (PRD F-S2): one per silent team, one capacity-gap header
// per district. The officer acknowledges ("I'm on it"), radios the team (Extend), or reassigns from the case.

import { useState } from "react";

import { Button } from "@/components/ui";
import { api, type Escalation } from "@/lib/api";

const CHANNELS = ["VHF", "HAM", "satellite", "phone"];

// "Heard on radio": the channel, and the ETA they gave (which also counts as their acknowledgement).
function Extend({ id, run }: { id: number; run: (fn: () => Promise<unknown>) => void }) {
  const [channel, setChannel] = useState("VHF");
  const send = (eta: number | null) => run(() => api(`/v1/escalations/${id}/extend`, { method: "POST", json: { channel, new_eta: eta } }));
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <select value={channel} onChange={(x) => setChannel(x.target.value)} aria-label="Heard on" className="h-7 rounded-lg border border-line bg-paper px-1.5 text-xs">
        {CHANNELS.map((c) => <option key={c}>{c}</option>)}
      </select>
      {[15, 30, 60].map((m) => <Button key={m} size="sm" variant={m === 30 ? "primary" : "secondary"} onClick={() => send(m)}>Heard · ETA {m}</Button>)}
      <Button size="sm" variant="quiet" onClick={() => send(null)}>Heard · no ETA</Button>
    </span>
  );
}

export function Escalations({ items, publicIds, onOpenCase, onChanged }: {
  items: Escalation[]; publicIds: (id: number) => string | undefined; onOpenCase: (id: number) => void; onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  if (!items.length) return null;
  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); onChanged(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <section aria-label="Alerts" className="mx-3 mt-3 space-y-2 rounded-2xl bg-wash p-2.5">
      {items.map((e) => (
        <div key={e.id} className="rounded-xl bg-paper p-3 shadow-[var(--shadow-card)] ring-1 ring-ink">
          <p className="text-sm font-medium leading-snug">{e.line}</p>
          <p className="mt-0.5 text-xs text-ink-3">
            For the {e.role === "incharge" ? "senior officer (nobody answered in time)" : "duty officer"}
            {e.status === "acked" && e.acked_by_name ? ` · ${e.acked_by_name} is on it` : ""}
          </p>
          {e.case_ids.length > 0 && (
            <p className="mt-1.5 flex flex-wrap gap-1">
              {e.case_ids.slice(0, 8).map((id) => (
                <button key={id} onClick={() => onOpenCase(id)} className="rounded-full border border-line px-2 text-xs tabular hover:bg-wash">{publicIds(id) ?? `#${id}`}</button>
              ))}
              {e.case_ids.length > 8 && <span className="text-xs text-ink-3">+{e.case_ids.length - 8}</span>}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            {e.status === "open" && <Button size="sm" onClick={() => run(() => api(`/v1/escalations/${e.id}/ack`, { method: "POST", json: {} }))}>I&rsquo;m on it</Button>}
            {e.kind === "team_overdue" && <Extend id={e.id} run={run} />}
          </div>
        </div>
      ))}
      {error && <p className="rounded-md bg-paper px-2 py-1 text-xs">{error}</p>}
    </section>
  );
}

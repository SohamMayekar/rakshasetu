"use client";

// "Needs you now" (PRD F-C2, F-C5). The order comes from the server's one rule; this component's job is
// that NOTHING MOVES UNDER THE CURSOR: rows already shown keep their place and update in place; new rows wait
// behind the "▲ 3 new: show" pill; rows that no longer need anyone fade where they are ("handled") until the
// person asks for the fresh list. The queue is the only alert surface: no toasts, no modals.

import { useEffect, useMemo, useState } from "react";

import { Button, Chip, Empty, Priority, PriorityWell } from "@/components/ui";
import type { Queue, QueueRow } from "@/lib/queue";

type Shown = QueueRow & { handled?: boolean };
const PAGE = 80;

export function NeedsYouNow({ queue, selected, onSelect, onAction }: {
  queue: Queue | null; selected: number | null; onSelect: (id: number) => void; onAction: (row: QueueRow) => void;
}) {
  const [shown, setShown] = useState<Shown[] | null>(null);
  // During a surge there can be thousands of rows: render them a page at a time (the order already puts what
  // matters first), so a click stays instant.
  const [limit, setLimit] = useState(PAGE);

  // Merge the latest server list into what's on screen without reordering it.
  useEffect(() => {
    if (!queue) return;
    setShown((prev) => {
      if (prev == null || prev.length === 0) return queue.rows;            // nothing under the cursor yet
      const latest = new Map(queue.rows.map((r) => [r.id, r]));
      return prev.map((r) => latest.get(r.id) ?? { ...r, handled: true });
    });
  }, [queue]);

  const waiting = useMemo(() => {
    if (!queue || !shown) return { fresh: 0, handled: 0 };
    const on = new Set(shown.map((r) => r.id));
    return { fresh: queue.rows.filter((r) => !on.has(r.id)).length, handled: shown.filter((r) => r.handled).length };
  }, [queue, shown]);

  if (!queue || !shown) return <Empty>Loading…</Empty>;
  const showAll = () => { setShown(queue.rows); setLimit(PAGE); };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-tight">
          Needs you now <span className="tabular rounded-full bg-wash px-2 py-0.5 text-xs font-semibold text-ink-2">{queue.rows.length}</span>
        </h2>
      </div>
      {(waiting.fresh > 0 || waiting.handled > 0) && (
        <div className="sticky top-0 z-10 py-1.5">
          <button onClick={showAll} className="mx-auto flex items-center gap-1 rounded-full bg-ink px-3 py-1 text-xs font-medium text-paper shadow-sm">
            <span aria-hidden>▲</span>
            <span className="tabular">
              {[waiting.fresh > 0 && `${waiting.fresh} new`, waiting.handled > 0 && `${waiting.handled} handled`].filter(Boolean).join(" · ")}: show
            </span>
          </button>
        </div>
      )}
      {shown.length === 0 ? (
        <Empty>Nothing needs you. <span className="tabular">{queue.on_it}</span> {queue.on_it === 1 ? "household has" : "households have"} a live owner.</Empty>
      ) : (
        <ol className="scroll-quiet flex-1 space-y-0.5 overflow-y-auto px-2 pb-2" aria-label="Needs you now">
          {shown.slice(0, limit).map((r) => (
            <li key={r.id} className={r.handled ? "stale" : ""}>
              <div role="button" tabIndex={0} onClick={() => onSelect(r.id)} onKeyDown={(e) => e.key === "Enter" && onSelect(r.id)}
                   aria-current={selected === r.id}
                   className={`flex w-full cursor-pointer gap-3 rounded-2xl px-2.5 py-2.5 text-left transition-colors hover:bg-wash ${selected === r.id ? "bg-wash ring-1 ring-line" : ""}`}>
                <PriorityWell level={r.priority} />
                <span className="block min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-baseline gap-2"><Priority level={r.priority} shape={false} />
                    {r.kind === "group" ? <span className="truncate font-semibold">Sheet · {r.public_id}</span> : <span className="tabular font-semibold">{r.public_id}</span>}
                  </span>
                  {r.handled ? <span className="text-xs text-ink-3">handled</span> : r.chip && <Chip tone="attention">{r.chip}</Chip>}
                </span>
                <span className="mt-0.5 block truncate text-sm">{r.line1}</span>
                {r.action.label.length > 22 ? (   // a long action ("Assign → SDRF Boat 2 · 2.1 km · boat") gets its own line
                  <>
                    <span className="block truncate text-xs text-ink-2">{r.line2}</span>
                    {!r.handled && <span className="mt-1.5 block"><Button size="sm" className="max-w-full truncate" onClick={(e) => { e.stopPropagation(); onAction(r); }}>{r.action.label}</Button></span>}
                  </>
                ) : (
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs text-ink-2">{r.line2}</span>
                    {!r.handled && <Button size="sm" className="shrink-0" onClick={(e) => { e.stopPropagation(); onAction(r); }}>{r.action.label}</Button>}
                  </span>
                )}
                </span>
              </div>
            </li>
          ))}
          {shown.length > limit && (
            <li className="p-3 text-center">
              <Button size="sm" onClick={() => setLimit(limit + 200)}>Show more ({shown.length - limit} below, in the same order)</Button>
            </li>
          )}
        </ol>
      )}
      <details className="border-t border-line px-4 py-2.5 text-sm text-ink-2">
        <summary className="cursor-pointer select-none">
          On it <span className="tabular">{queue.on_it}</span> · rescued, closing <span className="tabular">{queue.rescued_closing}</span> · closed <span className="tabular">{queue.closed}</span>
        </summary>
        <p className="mt-1 text-xs text-ink-3">Cases with a live owner whose check-in isn&rsquo;t due leave this list. They come back the moment a promise breaks.</p>
      </details>
    </div>
  );
}

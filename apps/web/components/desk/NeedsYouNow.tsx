"use client";

// "Needs you now" (PRD F-C2, F-C5). The order comes from the server's one rule; this component's job is
// that NOTHING MOVES UNDER THE CURSOR: rows already shown keep their place and update in place; new rows wait
// behind the "▲ 3 new: show" pill; rows that no longer need anyone fade where they are ("handled") until the
// person asks for the fresh list. The queue is the only alert surface: no toasts, no modals.

import { useEffect, useMemo, useState } from "react";

import { Button, Chip, Empty, Priority, PriorityWell } from "@/components/ui";
import type { Queue, QueueRow } from "@/lib/queue";
import { plainAction, plainChip, withWords } from "@/lib/words";

type Shown = QueueRow & { handled?: boolean };
const PAGE = 80;

// A row says four things (m67): the place, how many people, how long they've waited, and the one next step.
// The rest of the summary ("roof · water inside · medicine") is in the row's tooltip and the case panel.
function parts(r: QueueRow) {
  if (r.kind === "group") return { place: "", people: null, waiting: withWords(r.line2), owner: "" };   // "38 Urgent · 113 High · waiting 4 min"
  const bits = r.line2.split(" · ");
  const waiting = bits.find((b) => b.startsWith("waiting ")) ?? "";
  const place = bits[0] === "no location yet" ? "place not known" : bits[0];
  const owner = bits.slice(1).filter((b) => !b.startsWith("waiting ")).join(" · ");
  const people = r.line1?.match(/^~?\d+ (?:people|person)/)?.[0] ?? null;
  return { place, people, waiting, owner };
}

export function NeedsYouNow({ queue, selected, onSelect, onAction, tools }: {
  queue: Queue | null; selected: number | null; onSelect: (id: number) => void; onAction: (row: QueueRow) => void; tools?: React.ReactNode;
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
      <div className="flex items-center justify-between gap-2 px-4 pt-4 pb-2">
        <h2 className="flex items-center gap-2 whitespace-nowrap text-heading font-semibold tracking-tight">
          Needs you now
        </h2>
        {tools}
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
        <Empty>Nothing needs you. <span className="tabular">{queue.on_it}</span> {queue.on_it === 1 ? "family has" : "families have"} a team on it.</Empty>
      ) : (
        <ol className="scroll-quiet flex-1 divide-y divide-line overflow-y-auto px-2 pb-2" aria-label="Needs you now">
          {shown.slice(0, limit).map((r) => {
            // One row anatomy (m79): what and who, then which case and how long, then the one action, always at
            // the same left edge. Nothing truncates into the button.
            const { place, people, waiting, owner } = parts(r);
            const label = plainAction(r.action.label);
            const head = r.kind === "group" ? `Sheet · ${r.public_id}` : `${place}${people ? ` · ${people}` : ""}`;
            const sub = r.kind === "group" ? `${r.line1 ? withWords(r.line1) : ""} · ${waiting}` : `${r.public_id} · ${waiting}${owner ? ` · ${owner}` : ""}`;
            return (
              <li key={r.id} className={r.handled ? "stale" : ""}>
                <div role="button" tabIndex={0} onClick={() => onSelect(r.id)} onKeyDown={(e) => e.key === "Enter" && onSelect(r.id)}
                     aria-current={selected === r.id} title={r.line1 ?? undefined}
                     className={`my-1 flex w-full cursor-pointer gap-3 rounded-xl px-2.5 py-3 text-left transition-colors hover:bg-wash ${selected === r.id ? "bg-wash" : ""}`}>
                  <PriorityWell level={r.priority} />
                  <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <span className="flex items-start justify-between gap-2">
                      <span className="min-w-0 truncate text-body font-semibold leading-snug">{head}</span>
                      {r.handled ? <span className="shrink-0 text-small text-ink-3">handled</span> : r.chip && <Chip tone="attention">{plainChip(r.chip)}</Chip>}
                    </span>
                    <span className="truncate text-small text-ink-2"><Priority level={r.priority} shape={false} /> · {sub}</span>
                    {!r.handled && (
                      <span className="flex">
                        <Button size="sm" className="max-w-full truncate" onClick={(e) => { e.stopPropagation(); onAction(r); }}>{label}</Button>
                      </span>
                    )}
                  </span>
                </div>
              </li>
            );
          })}
          {shown.length > limit && (
            <li className="p-3 text-center">
              <Button size="sm" onClick={() => setLimit(limit + 200)}>Show more ({shown.length - limit} below, in the same order)</Button>
            </li>
          )}
        </ol>
      )}
    </div>
  );
}

"use client";

// The desk (PRD F-C2): queue on the left, map in the centre, the case drawer on the right. Live updates arrive
// in 1-second frames; the cases they name are re-read from the API (scoped), so the screen shows only what
// this user may see, and it is never more than a second behind the database.

import { use, useCallback, useEffect, useMemo, useState } from "react";

import { CaseMap } from "@/components/desk/CaseMap";
import { Drawer, type Picked } from "@/components/desk/Drawer";
import { Header } from "@/components/desk/Header";
import { NeedsYouNow } from "@/components/desk/NeedsYouNow";
import { api, ApiError, type Case, listCases, type Me } from "@/lib/api";
import { type Envelope, useLive } from "@/lib/live";
import type { Queue, QueueRow } from "@/lib/queue";

const CLOSED = new Set(["merged", "cancelled"]);

function caseIds(events: Envelope[]): number[] {
  const ids = new Set<number>();
  for (const e of events) {
    for (const k of ["case_id", "target_case_id", "source_case_id", "candidate_case_id"]) {
      const v = e.data?.[k];
      if (typeof v === "number") ids.add(v);
    }
  }
  return [...ids];
}

export default function Desk({ params }: { params: Promise<{ incident: string }> }) {
  const { incident } = use(params);
  const [me, setMe] = useState<Me | null>(null);
  const [cases, setCases] = useState<Map<number, Case>>(new Map());
  const [since, setSince] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [focus, setFocus] = useState<string | null>(null);
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<Picked>(null);
  const endPick = () => { setPicking(false); setPicked(null); };
  const loadQueue = useCallback(() => api<Queue>(`/v1/queue?incident=${encodeURIComponent(incident)}`).then(setQueue).catch(() => {}), [incident]);

  useEffect(() => {
    api<Me>("/v1/me").then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) location.href = "/login"; });
    listCases({ incident }).then(({ cases, seq }) => {
      setCases(new Map(cases.map((c) => [c.id, c])));
      setSince(seq);
      const want = new URLSearchParams(location.search).get("case");   // deep link: /desk/BR?case=BR-214
      const hit = want ? cases.find((c) => c.public_id === want || String(c.id) === want) : undefined;
      if (hit) setSelected(hit.id);
    })
      .catch((e) => { if (e instanceof ApiError && e.status === 401) location.href = "/login"; });
    loadQueue();
  }, [incident, loadQueue]);

  const onFrame = useCallback(async (events: Envelope[]) => {
    const ids = caseIds(events);
    if (!ids.length) return;
    loadQueue();
    const { cases: fresh } = await listCases({ ids });
    setCases((prev) => {
      const next = new Map(prev);
      for (const id of ids) next.delete(id);          // gone from scope (or merged away) unless re-read below
      for (const c of fresh) if (c.incident_code === incident) next.set(c.id, c);
      return next;
    });
  }, [incident, loadQueue]);
  const live = useLive(incident, since, onFrame);

  const open = useMemo(() => [...cases.values()].filter((c) => !CLOSED.has(c.status) && c.status !== "closed"), [cases]);
  // The map shows the queue's cases (and the selected one) in colour; every other open case is grey.
  const dim = useMemo(() => {
    const inQueue = new Set(queue?.rows.map((r) => r.id));
    return new Set(open.filter((c) => !inQueue.has(c.id) && c.id !== selected).map((c) => c.id));
  }, [open, queue, selected]);
  const current = selected != null ? cases.get(selected) ?? null : null;

  const onAction = useCallback(async (row: QueueRow) => {
    if (row.action.kind === "check") {      // the one action done straight from the row
      await api(`/v1/cases/${row.id}/check`, { method: "POST", json: {} }).catch(() => setFocus("Facts"));
      loadQueue();
      return;
    }
    setSelected(row.id);
    if (row.action.kind === "pin") { setPicking(true); setPicked(null); }
    setFocus({ pin: "Facts", match: "Timeline & evidence", radio: "Assignment", assign: "Assignment", open: null, check: null }[row.action.kind] ?? null);
  }, [loadQueue]);

  return (
    <div className="flex h-screen flex-col">
      <Header me={me} incident={incident} live={live} />
      <div className="flex min-h-0 flex-1">
        <nav className="w-full shrink-0 border-r border-line md:w-[380px]" aria-label="Needs you now">
          <NeedsYouNow queue={queue} selected={selected} onSelect={(id) => { setSelected(id); setFocus(null); }} onAction={onAction} />
        </nav>
        <main className="relative hidden min-w-0 flex-1 md:block">
          <CaseMap cases={open} selected={selected} dim={dim} onSelect={(id) => { if (!picking) setSelected(id); }}
                   picking={picking} picked={picked} onPick={setPicked} />
        </main>
        {current && <Drawer c={current} me={me} focus={focus} picking={picking} picked={picked}
                            onPickStart={() => { setPicking(true); setPicked(null); }} onPickEnd={endPick}
                            onClose={() => { setSelected(null); endPick(); }} />}
      </div>
    </div>
  );
}

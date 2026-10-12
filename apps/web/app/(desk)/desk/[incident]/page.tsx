"use client";

// The desk (PRD F-C2): queue on the left, map in the centre, the case drawer on the right. Live updates arrive
// in 1-second frames; the cases they name are re-read from the API (scoped), so the screen shows only what
// this user may see, and it is never more than a second behind the database.

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CaseMap } from "@/components/desk/CaseMap";
import { Drawer, type Picked } from "@/components/desk/Drawer";
import { Header } from "@/components/desk/Header";
import { PromiseBar, type QueueFilter } from "@/components/desk/PromiseBar";
import { NeedsYouNow } from "@/components/desk/NeedsYouNow";
import { ImportSheet } from "@/components/desk/ImportSheet";
import { NewReport } from "@/components/desk/NewReport";
import { FileSpreadsheet, Plus } from "lucide-react";

import { Sidebar } from "@/components/shell/Sidebar";
import { Button, Caption } from "@/components/ui";
import { caption } from "@/lib/caption";
import { Escalations } from "@/components/desk/Escalations";
import { api, ApiError, type Case, type Escalation, listCases, type Me, type Suggestion } from "@/lib/api";
import { type Envelope, useLive } from "@/lib/live";
import type { Queue, QueueRow } from "@/lib/queue";

const CLOSED = new Set(["merged", "cancelled"]);

function matches(r: QueueRow, f: QueueFilter): boolean {
  if (f === "p1_unowned") return r.priority === "P1" && !!r.chip && (r.chip.startsWith("no owner") || r.chip.includes("P1 without an owner"));   // copy-ok: the API's chip codes
  if (f === "overdue") return !!r.chip?.startsWith("contact overdue");
  if (f === "duplicates") return r.action.kind === "match";
  return true;
}

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
  const [composing, setComposing] = useState(false);
  const [importing, setImporting] = useState<{ id: number | null; filter?: string } | null>(null);
  const [saved, setSaved] = useState<{ reportId: number; line: string; caseId?: number } | null>(null);
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<Picked>(null);
  const endPick = () => { setPicking(false); setPicked(null); };
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [filter, setFilter] = useState<QueueFilter>(null);
  // One queue read at a time: in a surge, frames arrive every second and a read of 2,000+ rows mustn't pile up
  // behind itself. Asks that come in meanwhile collapse into one more read, 2 s after this one lands.
  const queueBusy = useRef(false);
  const queueAgain = useRef(false);
  const [matchesTick, setMatchesTick] = useState(0);
  const loadQueue = useCallback(() => {
    setMatchesTick((t) => t + 1);
    if (queueBusy.current) { queueAgain.current = true; return; }
    queueBusy.current = true;
    const q = encodeURIComponent(incident);
    Promise.all([
      api<Escalation[]>(`/v1/escalations?incident=${q}`).then(setEscalations).catch(() => setEscalations([])),
      api<Queue>(`/v1/queue?incident=${q}`).then(setQueue).catch(() => {}),
    ]).finally(() => {
      queueBusy.current = false;
      if (queueAgain.current) { queueAgain.current = false; setTimeout(loadQueue, 2000); }
    });
  }, [incident]);
  useEffect(() => {   // the open case's possible duplicates (the drawer's Matches), from either side of each pair
    if (selected == null) { setSuggestions([]); return; }
    api<Suggestion[]>(`/v1/merge-suggestions?case=${selected}`).then(setSuggestions).catch(() => setSuggestions([]));
  }, [selected, matchesTick]);

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

  // The judge-legibility caption: DEMO_MODE, the projector's local desk only, one sentence per frame (lib/caption).
  const [cap, setCap] = useState<string | null>(null);
  const capTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const seen = useRef({ me, cases });
  seen.current = { me, cases };
  useEffect(() => () => { if (capTimer.current) clearTimeout(capTimer.current); }, []);

  const onFrame = useCallback(async (events: Envelope[]) => {
    const { me: who, cases: known } = seen.current;
    if (who?.demo_mode && who.listener === "local") {
      const line = caption(events, (id) => known.get(id)?.public_id);
      if (line) {
        setCap(line);
        if (capTimer.current) clearTimeout(capTimer.current);
        capTimer.current = setTimeout(() => setCap(null), 9000);
      }
    }
    const ids = caseIds(events);
    if (events.some((e) => /^(escalation|team|assignment)\./.test(e.type))) { loadQueue(); setRefreshKey((k) => k + 1); }
    if (!ids.length) return;
    loadQueue();
    setSaved((sv) => {   // the report just saved from the form: which case did it become?
      if (!sv || sv.caseId) return sv;
      const made = events.find((e) => e.type === "case.created" && e.data?.report_id === sv.reportId);
      if (made) {
        api<Case>(`/v1/cases/${made.data.case_id}`).then((c) => {
          const kept = c.status === "merged" && c.parent_case_id ? c.parent_case_id : c.id;
          api<Case>(`/v1/cases/${kept}`).then((k) => {
            setSaved({ reportId: sv.reportId, caseId: k.id,
                       line: kept === c.id ? `→ ${k.public_id}, a new case` : `→ added to ${k.public_id} (the same family)` });
            setSelected(k.id);
          });
        }).catch(() => {});
      }
      return sv;
    });
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
  const dim = useMemo(() => {   // (not keyed on the selection: the selected circle is drawn bold on top anyway)
    const inQueue = new Set(queue?.rows.flatMap((r) => r.members ?? [r.id]));
    return new Set(open.filter((c) => !inQueue.has(c.id)).map((c) => c.id));
  }, [open, queue]);
  const current = selected != null ? cases.get(selected) ?? null : null;

  const onAction = useCallback(async (row: QueueRow) => {
    if (row.action.kind === "assign" && row.action.target) {   // one click: the top suggestion, as the button says
      try {
        await api("/v1/assignments", { method: "POST", json: { case: row.public_id, team_id: Number(row.action.target), suggested_rank: 1 } });
      } catch { setSelected(row.id); setFocus("Assignment"); }
      loadQueue();
      return;
    }
    if (row.action.kind === "check") {      // the one action done straight from the row
      await api(`/v1/cases/${row.id}/check`, { method: "POST", json: {} }).catch(() => setFocus("Facts"));
      loadQueue();
      return;
    }
    if (row.action.kind === "import") { setImporting({ id: Number(row.action.target), filter: "waiting" }); setComposing(false); return; }
    setSelected(row.id);
    setImporting(null);
    if (row.action.kind === "pin") { setPicking(true); setPicked(null); }
    setFocus({ pin: "Facts", match: "Timeline & evidence", radio: "Assignment", assign: "Assignment", open: null, check: null }[row.action.kind] ?? null);
  }, [loadQueue]);

  const card = "rounded-[20px] border border-line/80 bg-paper shadow-[var(--shadow-card)]";
  return (
    <div className="flex h-screen bg-canvas">
      <Sidebar me={me} compact />
      <div className="flex min-w-0 flex-1 flex-col gap-2.5 p-3 md:pl-0">
      <Header me={me} incident={incident} live={live} />
      {me?.permissions.includes("totals.view") && <PromiseBar incident={incident} onFilter={setFilter} />}
      <div className="flex min-h-0 flex-1 gap-2.5">
        <nav className={`flex w-full shrink-0 flex-col overflow-hidden md:w-[356px] ${card}`} aria-label="Needs you now">
          {saved && <p className="truncate px-4 pt-3 text-xs text-ink-2">Report saved {saved.line}</p>}
          <Escalations items={escalations} publicIds={(id) => cases.get(id)?.public_id}
                       onOpenCase={(id) => { setSelected(id); setFocus("Assignment"); setComposing(false); setImporting(null); }}
                       onChanged={loadQueue} />
          {filter && (
            <p className="mx-3 mt-2 flex items-center justify-between rounded-xl bg-wash px-3 py-1.5 text-xs">
              <span>Showing {{ p1_unowned: "urgent families without a team", overdue: "contact overdue", duplicates: "maybe repeats" }[filter]}</span>
              <button className="underline underline-offset-2" onClick={() => setFilter(null)}>Show all</button>
            </p>
          )}
          <NeedsYouNow key={filter ?? "all"} queue={queue && filter ? { ...queue, rows: queue.rows.filter((r) => matches(r, filter)) } : queue} selected={selected} onSelect={(id) => { if (id < 0) { setImporting({ id: -id, filter: "waiting" }); return; } setSelected(id); setFocus(null); setComposing(false); setImporting(null); }} onAction={onAction}
                       tools={me?.permissions.includes("report.submit") && (   // the two ways in for the desk itself: quiet, the rows' buttons come first
                         <span className="flex shrink-0 gap-1">
                           <Button size="sm" className="whitespace-nowrap" onClick={() => { setComposing(true); setImporting(null); setSelected(null); }}>
                             <Plus className="size-3.5" strokeWidth={2.4} aria-hidden />New report</Button>
                           {me?.permissions.includes("import.run") && (
                             <Button size="sm" variant="quiet" className="!px-2.5" title="Add a volunteer sheet (Excel or CSV)" onClick={() => { setImporting({ id: null }); setComposing(false); setSelected(null); }}>
                               <FileSpreadsheet className="size-4" strokeWidth={2} aria-hidden /><span className="sr-only">Add a sheet</span></Button>
                           )}
                         </span>
                       )} />
        </nav>
        <main className={`relative hidden min-w-0 flex-1 overflow-hidden md:block ${card}`}>
          <CaseMap cases={open} selected={selected} dim={dim} onSelect={(id) => { if (!picking) { setSelected(id); setComposing(false); } }}
                   picking={picking} picked={picked} onPick={setPicked} />
        </main>
        {importing && !composing && (
          <ImportSheet incident={incident} openId={importing.id} initialFilter={importing.filter}
                       onOpenCase={(id) => { setImporting(null); setSelected(id); }} onClose={() => setImporting(null)} />
        )}
        {composing && <NewReport incident={incident} onClose={() => setComposing(false)}
                                 onSaved={(id) => { setComposing(false); setSaved({ reportId: id, line: "· reading it…" }); }} />}
        {!composing && !importing && current && <Drawer c={current} me={me} focus={focus} picking={picking} picked={picked}
                            onPickStart={() => { setPicking(true); setPicked(null); }} onPickEnd={endPick}
                            onClose={() => { setSelected(null); endPick(); }}
                            suggestions={suggestions} lookup={(id) => cases.get(id)} onSelect={setSelected} onChanged={loadQueue}
                            escalations={escalations} refreshKey={refreshKey} />}
      </div>
      </div>
      <Caption text={cap} />
    </div>
  );
}

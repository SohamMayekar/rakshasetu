"use client";

// The desk (PRD F-C2): queue on the left, map in the centre, the case drawer on the right. Live updates arrive
// in 1-second frames; the cases they name are re-read from the API (scoped), so the screen shows only what
// this user may see, and it is never more than a second behind the database.

import { use, useCallback, useEffect, useMemo, useState } from "react";

import { CaseMap } from "@/components/desk/CaseMap";
import { Drawer, type Picked } from "@/components/desk/Drawer";
import { Header } from "@/components/desk/Header";
import { NeedsYouNow } from "@/components/desk/NeedsYouNow";
import { ImportSheet } from "@/components/desk/ImportSheet";
import { NewReport } from "@/components/desk/NewReport";
import { Button } from "@/components/ui";
import { api, ApiError, type Case, listCases, type Me, type Suggestion } from "@/lib/api";
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
  const [composing, setComposing] = useState(false);
  const [importing, setImporting] = useState<{ id: number | null; filter?: string } | null>(null);
  const [saved, setSaved] = useState<{ reportId: number; line: string; caseId?: number } | null>(null);
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<Picked>(null);
  const endPick = () => { setPicking(false); setPicked(null); };
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const loadQueue = useCallback(() => {
    api<Queue>(`/v1/queue?incident=${encodeURIComponent(incident)}`).then(setQueue).catch(() => {});
    api<Suggestion[]>(`/v1/merge-suggestions?incident=${encodeURIComponent(incident)}`).then(setSuggestions).catch(() => setSuggestions([]));
  }, [incident]);

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
    setSaved((sv) => {   // the report just saved from the form: which case did it become?
      if (!sv || sv.caseId) return sv;
      const made = events.find((e) => e.type === "case.created" && e.data?.report_id === sv.reportId);
      if (made) {
        api<Case>(`/v1/cases/${made.data.case_id}`).then((c) => {
          const kept = c.status === "merged" && c.parent_case_id ? c.parent_case_id : c.id;
          api<Case>(`/v1/cases/${kept}`).then((k) => {
            setSaved({ reportId: sv.reportId, caseId: k.id,
                       line: kept === c.id ? `→ ${k.public_id}, a new case` : `→ folded into ${k.public_id} (the same household)` });
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
  const dim = useMemo(() => {
    const inQueue = new Set(queue?.rows.flatMap((r) => r.members ?? [r.id]));
    return new Set(open.filter((c) => !inQueue.has(c.id) && c.id !== selected).map((c) => c.id));
  }, [open, queue, selected]);
  const current = selected != null ? cases.get(selected) ?? null : null;

  const onAction = useCallback(async (row: QueueRow) => {
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

  return (
    <div className="flex h-screen flex-col">
      <Header me={me} incident={incident} live={live} />
      <div className="flex min-h-0 flex-1">
        <nav className="flex w-full shrink-0 flex-col border-r border-line md:w-[380px]" aria-label="Needs you now">
          {me?.permissions.includes("report.submit") && (
            <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2">
              <span className="flex shrink-0 gap-1.5">
                <Button size="sm" variant="primary" className="whitespace-nowrap" onClick={() => { setComposing(true); setImporting(null); setSelected(null); }}>New report</Button>
                {me?.permissions.includes("import.run") && (
                  <Button size="sm" className="whitespace-nowrap" onClick={() => { setImporting({ id: null }); setComposing(false); setSelected(null); }}>Import sheet</Button>
                )}
              </span>
              {saved && <span className="truncate text-xs text-ink-2">Report saved {saved.line}</span>}
            </div>
          )}
          <NeedsYouNow queue={queue} selected={selected} onSelect={(id) => { if (id < 0) { setImporting({ id: -id, filter: "waiting" }); return; } setSelected(id); setFocus(null); setComposing(false); setImporting(null); }} onAction={onAction} />
        </nav>
        <main className="relative hidden min-w-0 flex-1 md:block">
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
                            suggestions={suggestions} lookup={(id) => cases.get(id)} onSelect={setSelected} onChanged={loadQueue} />}
      </div>
    </div>
  );
}

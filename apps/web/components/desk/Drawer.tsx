"use client";

// The case drawer (PRD F-C2), titled with the PS's words: Assignment · Facts · Timeline & evidence · Audit.
// It re-reads the case whenever a live update changes it, and offers only the actions this role may take.

import { useCallback, useEffect, useRef, useState } from "react";

import { AssignmentPanel } from "@/components/desk/AssignmentPanel";
import { Facts } from "@/components/desk/Facts";
import { Matches } from "@/components/desk/Matches";
import { Timeline } from "@/components/desk/Timeline";
import { ArrowUpDown, ClipboardCheck, History, MapPin, ShieldCheck, Users, X } from "lucide-react";

import { Because, Button, Chip, Priority, PriorityWell, Section } from "@/components/ui";
import { priorityWord, withWords } from "@/lib/words";
import { api, type Case, type CaseDetail, type Escalation, type Evidence, type Me, type PartnerNote, type Suggestion, type TimelineEvent } from "@/lib/api";

export type Picked = { lat: number; lng: number } | null;

const STATUS_WORD: Record<string, string> = { checked: "checked", assigned: "a team has it", reached: "team reached", partial: "some still there",
  rescued: "rescued", closed: "closed", cancelled: "cancelled", merged: "added to another case", acknowledged: "team accepted" };

// An officer's decisions on a case, each with a reason (PRD §5.2): close, cancel, reopen.
function Decide({ c, onDone }: { c: Case; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const kinds = ["closed", "cancelled", "rescued"].includes(c.status) ? ["reopen"] : ["close", "cancel"];
  if (!open) return <Button size="sm" variant="quiet" onClick={() => setOpen(true)}>{kinds[0] === "reopen" ? "Reopen…" : "Close or cancel…"}</Button>;
  return (
    <form className="mt-2 flex w-full flex-wrap gap-2" onSubmit={async (e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      try { await api(`/v1/cases/${c.id}/${f.get("kind")}`, { method: "POST", json: { reason: String(f.get("reason")) } }); setOpen(false); onDone(); }
      catch (x) { setError(x instanceof Error ? x.message : String(x)); }
    }}>
      <select name="kind" className="h-8 rounded-lg border border-line bg-paper px-2 text-sm">{kinds.map((k) => <option key={k} value={k}>{{ close: "close", cancel: "cancel (not a real request)", reopen: "reopen" }[k]}</option>)}</select>
      <input name="reason" required minLength={3} autoFocus placeholder="Why (logged)" className="h-8 min-w-0 flex-1 rounded-lg border border-line px-2 text-sm" />
      <Button size="sm" variant="primary" type="submit">Confirm</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-xs">{error}</span>}
    </form>
  );
}

// P1 #2: the officer raises or lowers the priority, with a reason everyone sees; or hands it back to the rules.
type Override = { level: string; from: string; rules_said: string; by: string; reason: string } | null;
function PriorityCall({ c, onDone }: { c: Case; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const o = c.priority_override as Override;
  if (!open) return <Button size="sm" variant="quiet" onClick={() => setOpen(true)}><ArrowUpDown className="size-3.5" aria-hidden />Change priority…</Button>;
  return (
    <form className="mt-2 flex w-full flex-wrap gap-2" onSubmit={async (e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      const level = String(f.get("level"));
      try {
        await api(`/v1/cases/${c.id}/priority`, { method: "POST", json: { priority: level === "rules" ? null : level, reason: String(f.get("reason")) } });
        setOpen(false); onDone();
      } catch (x) { setError(x instanceof Error ? x.message : String(x)); }
    }}>
      <select name="level" defaultValue={c.priority} className="h-8 rounded-lg border border-line bg-paper px-2 text-sm">
        {["P1", "P2", "P3", "P4"].map((l) => <option key={l} value={l}>{priorityWord(l)} ({l})</option>)}
        {o && <option value="rules">back to the rules</option>}
      </select>
      <input name="reason" required minLength={3} autoFocus placeholder="Why (shown on the case)" className="h-8 min-w-0 flex-1 rounded-lg border border-line px-2 text-sm" />
      <Button size="sm" variant="primary" type="submit">Confirm</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-xs">{error}</span>}
    </form>
  );
}

// A person can merge any two cases they can see, with a reason; the older one is kept (undoable).
function ManualMerge({ c, onDone }: { c: Case; onDone: (kept: number) => void }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!open) return <div className="mt-3"><Button size="sm" variant="quiet" onClick={() => setOpen(true)}>Same family as another case…</Button></div>;
  return (
    <form className="mt-3 flex flex-wrap gap-2 rounded-lg border border-line p-3" onSubmit={async (e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      try {
        const r = await api<{ kept: string }>("/v1/merges", { method: "POST", json: { cases: [c.public_id, String(f.get("other")).trim().toUpperCase()], reason: String(f.get("reason")) } });
        const kept = await api<Case>(`/v1/cases/${encodeURIComponent(r.kept)}`);
        setOpen(false); onDone(kept.id);
      } catch (x) { setError(x instanceof Error ? x.message : String(x)); }
    }}>
      <input name="other" required placeholder="BR-214" className="h-8 w-24 rounded-lg border border-line px-2 text-sm tabular" autoFocus />
      <input name="reason" required minLength={3} placeholder="Why (logged)" className="h-8 min-w-0 flex-1 rounded-lg border border-line px-2 text-sm" />
      <Button size="sm" variant="primary" type="submit">Merge</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-xs">{error}</span>}
    </form>
  );
}

export function Drawer({ c, me, focus, picking, picked, onPickStart, onPickEnd, onClose, suggestions, lookup, onSelect, onChanged, escalations = [], refreshKey = 0 }: {
  c: Case; me: Me | null; focus?: string | null; picking: boolean; picked: Picked;
  onPickStart: () => void; onPickEnd: () => void; onClose: () => void;
  suggestions: Suggestion[]; lookup: (id: number) => Case | undefined; onSelect: (id: number) => void; onChanged: () => void;
  escalations?: Escalation[]; refreshKey?: number;
}) {
  const can = (a: string) => !!me?.permissions.includes(a);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [tl, setTl] = useState<{ events: TimelineEvent[]; evidence: Evidence[] } | null>(null);
  const [notes, setNotes] = useState<PartnerNote[]>([]);
  const [quote, setQuote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const body = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    api<CaseDetail>(`/v1/cases/${c.id}`).then(setDetail).catch(() => {});
    api<{ events: TimelineEvent[]; evidence: Evidence[] }>(`/v1/cases/${c.id}/timeline`).then(setTl).catch(() => {});
    api<PartnerNote[]>(`/v1/cases/${c.id}/annotations`).then(setNotes).catch(() => setNotes([]));
  }, [c.id]);
  useEffect(load, [load, c.version, c.updated_at, refreshKey]);   // refreshKey: a live event about this case
  useEffect(() => { setError(null); }, [c.id]);

  useEffect(() => {   // open at the section the queue's action asked for
    if (!focus || !body.current) return;
    body.current.querySelector(`[data-section="${focus}"]`)?.scrollIntoView({ block: "start" });
  }, [focus, c.id, tl]);

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); load(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const savePin = (form: FormData) => act(async () => {
    await api(`/v1/cases/${c.id}/location`, { method: "PATCH", json: { lat: picked!.lat, lng: picked!.lng, reason: String(form.get("reason")) } });
    onPickEnd();
  });

  return (
    <aside className="fixed inset-0 z-40 flex flex-col overflow-hidden bg-paper md:static md:h-full md:w-[440px] md:shrink-0 md:rounded-[20px] md:border md:border-line/80 md:shadow-[var(--shadow-card)]" aria-label={`Case ${c.public_id}`}>
      <div className="m-3 mb-0 rounded-2xl bg-wash px-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <PriorityWell level={c.priority} size="lg" />
            <div className="min-w-0">
              <p className="flex flex-wrap items-baseline gap-2">
                <Priority level={c.priority} shape={false} />
                <span className="tabular text-xl font-semibold tracking-tight">{c.public_id}</span>
              </p>
              <p className="mt-0.5 flex flex-wrap gap-1.5">
                <Chip tone="neutral">{c.status === "reported" ? "not checked yet" : STATUS_WORD[c.status] ?? c.status}</Chip>
                {c.status !== "reported" && !c.checked_at && <Chip tone="neutral">not checked yet</Chip>}
                {c.flags.includes("instruction_like_text") && <Chip tone="attention">words that look like orders: read them</Chip>}
              </p>
            </div>
          </div>
          <Button variant="quiet" size="sm" onClick={onClose} aria-label="Close" title="Close"><X className="size-4" aria-hidden />Close</Button>
        </div>
        <p className="mt-3 text-[15px] font-medium">{c.summary}</p>
        {(c.priority_override as Override)
          ? <Because>{c.priority} · {(() => { const o = c.priority_override as NonNullable<Override>;
              return `${o.level < o.from ? "raised" : o.level > o.from ? "lowered" : "kept"} by ${o.by}: “${o.reason}” · the rules said ${priorityWord(o.rules_said)}`; })()}</Because>
          : c.priority_reasons.length > 0 && <Because>{priorityWord(c.priority)} · {c.priority_reasons.join(" · ")}</Because>}
        {notes.filter((n) => n.kind === "priority").map((n) => (   // a partner suggests; an officer decides
          <div key={n.id} className="mt-3 rounded-xl border border-line bg-paper px-3 py-2.5 text-sm">
            <p><b>{n.team}</b> suggests <b>{withWords(String(n.value))}</b>{n.confidence != null ? ` · ${n.confidence.toFixed(2)}` : ""}{n.explanation ? ` · ${n.explanation}` : ""}</p>
            {n.decision ? <p className="text-xs text-ink-3">{n.decision} by an officer</p>
              : can("priority.override") && (
                <p className="mt-1.5 flex gap-2">
                  <Button size="sm" variant="primary" onClick={() => act(() => api(`/v1/partner-annotations/${n.id}/accept`, { method: "POST", json: {} }))}>Accept</Button>
                  <Button size="sm" onClick={() => act(() => api(`/v1/partner-annotations/${n.id}/ignore`, { method: "POST", json: {} }))}>Ignore</Button>
                </p>
              )}
          </div>
        ))}
        <div className="mt-3 flex flex-wrap gap-2">
          {!c.checked_at && can("case.check") && (
            <Button size="sm" variant="primary" onClick={() => act(() => api(`/v1/cases/${c.id}/check`, { method: "POST", json: {} }))}>
              <ClipboardCheck className="size-3.5" aria-hidden />Mark checked</Button>
          )}
          {can("case.move_pin") && !picking && <Button size="sm" onClick={onPickStart}><MapPin className="size-3.5" aria-hidden />Move the place</Button>}
          {can("priority.override") && !["merged", "closed", "cancelled"].includes(c.status) && <PriorityCall c={c} onDone={() => { onChanged(); load(); }} />}
          {can("case.decide") && <Decide c={c} onDone={() => { onChanged(); load(); }} />}
        </div>
        {picking && (
          <form className="mt-3 space-y-2 rounded-xl border border-line bg-paper p-3 text-sm" onSubmit={(e) => { e.preventDefault(); savePin(new FormData(e.currentTarget)); }}>
            <p>{picked ? <>New place at <span className="tabular">{picked.lat.toFixed(5)}, {picked.lng.toFixed(5)}</span> · a person placed it, so its circle is 50 m.</>
                       : "Click the map where the household is."}</p>
            {picked && <input name="reason" required minLength={3} placeholder="Why (logged), e.g. caller confirmed on phone" className="h-8 w-full rounded-lg border border-line px-2" autoFocus />}
            <div className="flex gap-2">
              {picked && <Button size="sm" variant="primary" type="submit">Save the place</Button>}
              <Button size="sm" variant="quiet" type="button" onClick={onPickEnd}>Cancel</Button>
            </div>
          </form>
        )}
        {error && <p className="mt-2 rounded-lg bg-paper px-2 py-1 text-xs">{error}</p>}
      </div>
      <div ref={body} className="scroll-quiet flex-1 overflow-y-auto px-5">
        <div data-section="Assignment">
          <Section title="Assignment" icon={Users}>
            {detail ? <AssignmentPanel c={c} assignment={detail.assignment}
                                       escalation={escalations.find((e) => e.kind === "team_overdue" && e.case_ids.includes(c.id))}
                                       can={can} onChanged={() => { onChanged(); load(); }} />
                    : <p className="text-sm text-ink-3">Loading…</p>}
          </Section>
        </div>
        <div data-section="Facts">
          <Section title="Facts" icon={ClipboardCheck}>
            <Facts c={c} canEdit={can("case.edit")} onQuote={setQuote} onChanged={load} />
            {detail?.reports[0]?.reporter_phone_masked && (
              <p className="mt-2 text-sm"><span className="text-ink-3">Contact</span> <span className="tabular">{detail.reports[0].reporter_phone_masked}</span>
                {detail.reports[0].reporter_relation && detail.reports[0].reporter_relation !== "unknown" && <span className="text-ink-3"> · {detail.reports[0].reporter_relation}</span>}</p>
            )}
          </Section>
        </div>
        <div data-section="Timeline & evidence">
          <Section title="Timeline & evidence" icon={History}>
            <Matches c={c} suggestions={suggestions} lookup={lookup} canDecide={can("merge.decide")}
                     onDone={(kept) => { onChanged(); load(); if (kept && kept !== c.id) onSelect(kept); }} />
            {tl && detail ? <Timeline events={tl.events} evidence={tl.evidence} reports={detail.reports} quote={quote} notes={notes}
                                      canUndo={can("merge.decide")} onChanged={() => { onChanged(); load(); }} />
                          : <p className="text-sm text-ink-3">Loading…</p>}
            {can("merge.decide") && <ManualMerge c={c} onDone={(kept) => { onChanged(); load(); if (kept !== c.id) onSelect(kept); }} />}
          </Section>
        </div>
        <div data-section="Audit">
          <Section title="Audit" icon={ShieldCheck}>
            <p className="text-sm text-ink-2">Every change to this case is written down in order, and nobody can edit the past unnoticed.</p>
            <a className="mt-1 inline-block text-sm underline underline-offset-2" href={`/audit?case=${c.id}`}>See this case&rsquo;s full history</a>
          </Section>
        </div>
      </div>
    </aside>
  );
}

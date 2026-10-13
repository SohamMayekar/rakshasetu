"use client";

// The case panel (PRD F-C2). It opens on a summary (m68): who and how many, where (with the honest circle), the
// status in plain words, and ONE next-step button chosen by the same rule as the queue's action. Below it, the
// PS's sections, collapsed: Assignment · Facts · Timeline & evidence · Audit (one click each; a queue action opens
// the one it needs). Moving the place, the priority call, close/cancel are under More. It re-reads the case
// whenever a live update changes it, and offers only the actions this role may take.

import { useCallback, useEffect, useRef, useState } from "react";

import { AssignmentPanel } from "@/components/desk/AssignmentPanel";
import { Facts } from "@/components/desk/Facts";
import { Matches } from "@/components/desk/Matches";
import { Timeline } from "@/components/desk/Timeline";
import { ArrowUpDown, ChevronDown, ClipboardCheck, History, MapPin, Users, X, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Because, Button, Chip, Priority } from "@/components/ui";
import { plainPlace, priorityWord, withWords } from "@/lib/words";
import { api, type Assignment, type Case, type CaseDetail, type Escalation, type Evidence, type Me, type PartnerNote,
         type Suggestion, type TimelineEvent } from "@/lib/api";

export type Picked = { lat: number; lng: number } | null;

// A section in the PS's words that opens and closes; the header says what is inside in a few words.
function Fold({ title, icon: Icon, hint, open, onToggle, children }: {
  title: string; icon: LucideIcon; hint?: string; open: boolean; onToggle: () => void; children: ReactNode;
}) {
  return (
    <section data-section={title} className="border-t border-line first:border-t-0">
      <button onClick={onToggle} aria-expanded={open} className="flex min-h-12 w-full items-center gap-2.5 py-3 text-left">
        <Icon className="size-4 shrink-0 text-ink-3" strokeWidth={1.8} aria-hidden />
        <span className="shrink-0 text-body font-semibold">{title}</span>
        {hint && !open && <span className="min-w-0 flex-1 truncate text-small text-ink-3">{hint}</span>}
        <ChevronDown className={`ml-auto size-4 shrink-0 text-ink-3 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && <div className="pb-6 pt-1">{children}</div>}
    </section>
  );
}

const hhmm = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
const within = (m: number | null) => (m == null ? "" : m >= 1000 ? `within ${m / 1000} km` : `within ${m} m`);
function waited(iso: string) {
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${min % 60} min`;
}

// Who the case is about, when the report gave a name ("Devesh"); never invented.
function callerName(c: Case): string {
  const names = ((c.provenance ?? {}) as Record<string, unknown>).names;
  const first = Array.isArray(names) ? (names[0] as { value?: unknown } | undefined) : undefined;
  return typeof first?.value === "string" && first.value.trim() ? first.value : "A family";
}

// The RESCUE block: only states the application really has (PRD F-C4/F-S1) — no invented "en route".
function rescueState(c: Case, a: Assignment | null): { line: string; detail: string } {
  if (c.status === "rescued") return { line: "Outcome recorded", detail: c.people_count ? `Rescued ${c.people_count} of ${c.people_count}` : "Rescued" };
  if (c.status === "closed") return { line: "Closed", detail: "the officer closed this case" };
  if (c.status === "cancelled") return { line: "Cancelled", detail: "not a real request" };
  if (c.status === "merged") return { line: "Added to another case", detail: "the same family" };
  if (!a) return { line: "No team assigned", detail: `waiting ${waited(c.queue_since)}` };
  if (a.state === "overdue") return { line: "Contact overdue", detail: `${a.team} · not heard since ${hhmm(a.last_contact_at ?? a.created_at)}` };
  if (a.phase === "offered") return { line: "Dispatch issued", detail: `${a.team} · awaiting acknowledgement` };
  if (a.phase === "acknowledged") return { line: "Acknowledged", detail: `${a.team}${a.eta_minutes ? ` · there in about ${a.eta_minutes} min` : ""}` };
  if (a.phase === "reached") return { line: "Arrived", detail: `${a.team} · reached the family` };
  return { line: a.phase, detail: a.team };
}


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
      <select name="kind" className="field-compact">{kinds.map((k) => <option key={k} value={k}>{{ close: "close", cancel: "cancel (not a real request)", reopen: "reopen" }[k]}</option>)}</select>
      <input name="reason" required minLength={3} autoFocus placeholder="Why (logged)" className="field-compact min-w-0 flex-1" />
      <Button size="sm" variant="primary" type="submit">Confirm</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-small">{error}</span>}
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
      <select name="level" defaultValue={c.priority} className="field-compact">
        {["P1", "P2", "P3", "P4"].map((l) => <option key={l} value={l}>{priorityWord(l)} ({l})</option>)}
        {o && <option value="rules">back to the rules</option>}
      </select>
      <input name="reason" required minLength={3} autoFocus placeholder="Why (shown on the case)" className="field-compact min-w-0 flex-1" />
      <Button size="sm" variant="primary" type="submit">Confirm</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-small">{error}</span>}
    </form>
  );
}

// A person can merge any two cases they can see, with a reason; the older one is kept (undoable).
function ManualMerge({ c, onDone }: { c: Case; onDone: (kept: number) => void }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!open) return <div className="mt-3"><Button size="sm" variant="quiet" onClick={() => setOpen(true)}>Same family as another case…</Button></div>;
  return (
    <form className="mt-3 flex flex-wrap gap-2 rounded-xl border border-line p-3" onSubmit={async (e) => {
      e.preventDefault();
      const f = new FormData(e.currentTarget);
      try {
        const r = await api<{ kept: string }>("/v1/merges", { method: "POST", json: { cases: [c.public_id, String(f.get("other")).trim().toUpperCase()], reason: String(f.get("reason")) } });
        const kept = await api<Case>(`/v1/cases/${encodeURIComponent(r.kept)}`);
        setOpen(false); onDone(kept.id);
      } catch (x) { setError(x instanceof Error ? x.message : String(x)); }
    }}>
      <input name="other" required placeholder="CASE-214" className="field-compact w-24 tabular" autoFocus />
      <input name="reason" required minLength={3} placeholder="Why (logged)" className="field-compact min-w-0 flex-1" />
      <Button size="sm" variant="primary" type="submit">Merge</Button>
      <Button size="sm" variant="quiet" type="button" onClick={() => setOpen(false)}>Cancel</Button>
      {error && <span className="w-full text-small">{error}</span>}
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

  // The sections start closed; the queue's action opens the one it needs, and scrolls to it.
  const [opened, setOpened] = useState<Set<string>>(new Set(focus ? [focus] : []));
  const [more, setMore] = useState(false);
  const toggle = (name: string) => setOpened((o) => { const n = new Set(o); if (n.has(name)) n.delete(name); else n.add(name); return n; });
  const show = useCallback((name: string) => {
    setOpened((o) => new Set(o).add(name));
    setTimeout(() => body.current?.querySelector(`[data-section="${name}"]`)?.scrollIntoView({ block: "start" }), 50);
  }, []);
  useEffect(() => { setOpened(new Set(focus ? [focus] : [])); setMore(false); }, [c.id]);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (focus) show(focus); }, [focus, c.id, show]);

  // The best team, for the summary's one button when nobody has the case yet (the same list as Assignment's).
  const owned = !!detail?.assignment;

  const act = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); load(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const savePin = (form: FormData) => act(async () => {
    await api(`/v1/cases/${c.id}/location`, { method: "PATCH", json: { lat: picked!.lat, lng: picked!.lng, reason: String(form.get("reason")) } });
    onPickEnd();
  });

  // ONE next step, by the queue's rule: an answer owed, a silent team, the place, a possible repeat, the teams, the check.
  const a = detail?.assignment ?? null;
  const open = !["merged", "closed", "cancelled", "rescued"].includes(c.status);
  const repeat = suggestions.find((x) => x.strength !== "refused" && (x.case_id === c.id || x.candidate_case_id === c.id));
  const unchecked = !c.checked_at && can("case.check");
  const check = () => act(() => api(`/v1/cases/${c.id}/check`, { method: "POST", json: {} }));
  const next: { label: string; run: () => void } | null =
    !open ? null
    : c.flags.includes("disputed") ? { label: "Radio the team", run: () => show("Assignment") }
    : a?.state === "overdue" && can("team.radio_contact") ? { label: "Heard from them?", run: () => show("Assignment") }
    : c.lat == null && can("case.move_pin") ? { label: "Fix the place", run: onPickStart }
    : repeat && can("merge.decide") ? { label: `Same family as ${repeat.case_id === c.id ? repeat.candidate : repeat.public_id}?`, run: () => show("Report details") }
    : !a && can("assignment.create") ? { label: "Find suitable rescue teams", run: () => show("Assignment") }
    : unchecked ? { label: "Mark checked", run: check }
    : null;
  const evidenceCount = tl?.evidence.length ?? 0;

  return (
    <aside className="panel-in fixed inset-0 z-40 flex flex-col overflow-hidden bg-paper md:static md:h-full md:w-[440px] md:shrink-0 md:rounded-card md:border md:border-line/80 md:shadow-[var(--shadow-card)]" aria-label={`Case ${c.public_id}`}>
      <div ref={body} className="scroll-quiet flex-1 overflow-y-auto">
      <div className="m-3 mb-0 rounded-xl bg-wash p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-title font-semibold leading-tight">{callerName(c)} needs rescue</p>
            <p className="mt-1 flex flex-wrap items-baseline gap-2">
              <span className="tabular text-body font-semibold text-ink-2">{c.public_id}</span>
              <Priority level={c.priority} shape={false} />
            </p>
          </div>
          <Button variant="quiet" size="sm" onClick={onClose} aria-label="Close" title="Close"><X className="size-4" aria-hidden />Close</Button>
        </div>
        <p className="mt-3 text-body">
          Caller reports {c.summary || "an emergency"}{c.location_text ? <> at <b>{c.location_text}</b></> : null}.
        </p>
        <div className="mt-4 space-y-3 text-body">
          <div>
            <p className="text-small font-semibold uppercase tracking-wide text-ink-3">Location</p>
            <p className="mt-0.5">
              {c.location_text ?? "Not known yet"}
              {c.radius_m ? <span className="text-ink-2"> · {within(c.radius_m)}</span> : null}
            </p>
            <p className="text-small text-ink-2">
              {c.checked_at ? "Verified by a person" : c.lat == null ? "Where exactly? a person must place it" : "Location needs verification"}
            </p>
            {c.location_method && <p className="text-small text-ink-3">{plainPlace(c.location_method).replace(/^within [^:]+: /, "")}</p>}
            {c.lat != null && c.lng != null && (
              <a href={`https://www.google.com/maps/search/?api=1&query=${c.lat},${c.lng}`} target="_blank" rel="noreferrer"
                 className="mt-1 inline-flex items-baseline gap-1.5 text-small font-medium text-ink underline underline-offset-4">
                The exact pin on Google Maps
                <span className="tabular text-ink-3">{c.lat.toFixed(5)}, {c.lng.toFixed(5)}</span>
              </a>
            )}
          </div>
          <div>
            <p className="text-small font-semibold uppercase tracking-wide text-ink-3">Rescue</p>
            <p className="mt-0.5">
              <span className={a?.state === "overdue" ? "rounded-md bg-ink px-1.5 text-paper" : "font-semibold"}>{rescueState(c, a).line}</span>
              <span className="text-ink-2"> · {rescueState(c, a).detail}</span>
            </p>
          </div>
        </div>
        {c.flags.includes("instruction_like_text") && <p className="mt-2"><Chip tone="attention">words that look like orders: read them</Chip></p>}
        {notes.filter((n) => n.kind === "priority").map((n) => (   // a partner suggests; an officer decides
          <div key={n.id} className="mt-3 rounded-xl border border-line bg-paper px-3 py-2.5 text-body">
            <p><b>{n.team}</b> suggests <b>{withWords(String(n.value))}</b>{n.confidence != null ? ` · ${n.confidence.toFixed(2)}` : ""}{n.explanation ? ` · ${n.explanation}` : ""}</p>
            {n.decision ? <p className="text-small text-ink-3">{n.decision} by an officer</p>
              : can("priority.override") && (
                <p className="mt-1.5 flex gap-2">
                  <Button size="sm" variant="primary" onClick={() => act(() => api(`/v1/partner-annotations/${n.id}/accept`, { method: "POST", json: {} }))}>Accept</Button>
                  <Button size="sm" onClick={() => act(() => api(`/v1/partner-annotations/${n.id}/ignore`, { method: "POST", json: {} }))}>Ignore</Button>
                </p>
              )}
          </div>
        ))}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {next && <Button variant="primary" onClick={next.run}>{next.label}</Button>}
          <Button size="sm" variant="quiet" onClick={() => setMore(!more)} aria-expanded={more}>{more ? "Less" : "More"}</Button>
        </div>
        {more && (
          <div className="mt-2 space-y-2 border-t border-line pt-3">
            {(c.priority_override as Override)
              ? <Because>{priorityWord(c.priority)} · {(() => { const o = c.priority_override as NonNullable<Override>;
                  return `${o.level < o.from ? "raised" : o.level > o.from ? "lowered" : "kept"} by ${o.by}: “${o.reason}” · the rules said ${priorityWord(o.rules_said)}`; })()}</Because>
              : c.priority_reasons.length > 0 && <Because>{priorityWord(c.priority)} · {c.priority_reasons.join(" · ")}</Because>}
            <div className="flex flex-wrap gap-2">
              {unchecked && next?.label !== "Mark checked" && (
                <Button size="sm" onClick={check}><ClipboardCheck className="size-3.5" aria-hidden />Mark checked</Button>
              )}
              {can("case.move_pin") && !picking && <Button size="sm" onClick={onPickStart}><MapPin className="size-3.5" aria-hidden />Move the place</Button>}
              {can("priority.override") && open && <PriorityCall c={c} onDone={() => { onChanged(); load(); }} />}
              {can("case.decide") && <Decide c={c} onDone={() => { onChanged(); load(); }} />}
            </div>
          </div>
        )}
        {picking && (
          <form className="mt-3 space-y-2 rounded-xl border border-line bg-paper p-3 text-body" onSubmit={(e) => { e.preventDefault(); savePin(new FormData(e.currentTarget)); }}>
            <p>{picked ? <>New place at <span className="tabular">{picked.lat.toFixed(5)}, {picked.lng.toFixed(5)}</span> · a person placed it, so its circle is 50 m.</>
                       : "Click the map where the family is."}</p>
            {picked && <input name="reason" required minLength={3} placeholder="Why (logged), e.g. caller confirmed on phone" className="field-compact w-full" autoFocus />}
            <div className="flex gap-2">
              {picked && <Button size="sm" variant="primary" type="submit">Save the place</Button>}
              <Button size="sm" variant="quiet" type="button" onClick={onPickEnd}>Cancel</Button>
            </div>
          </form>
        )}
        {error && <p className="mt-2 rounded-xl bg-paper px-2 py-1 text-small">{error}</p>}
      </div>
      <div className="px-5 pt-1">
        <Fold title="Assignment" icon={Users} open={opened.has("Assignment")} onToggle={() => toggle("Assignment")}
              hint={a ? `${a.team}` : "no team yet"}>
          {detail ? <AssignmentPanel c={c} assignment={detail.assignment}
                                     escalation={escalations.find((e) => e.kind === "team_overdue" && e.case_ids.includes(c.id))}
                                     can={can} onChanged={() => { onChanged(); load(); }} />
                  : <p className="text-body text-ink-3">Loading…</p>}
        </Fold>
        <Fold title="Report details" icon={ClipboardCheck} open={opened.has("Report details")} onToggle={() => toggle("Report details")}
              hint="the caller's words, the facts read from them, contact">
          <Facts c={c} canEdit={can("case.edit")} onQuote={setQuote} onChanged={load} />
          {detail?.reports[0]?.reporter_phone_masked && (
            <p className="mt-2 text-body"><span className="text-ink-3">Contact</span> <span className="tabular">{detail.reports[0].reporter_phone_masked}</span>
              {detail.reports[0].reporter_relation && detail.reports[0].reporter_relation !== "unknown" && <span className="text-ink-3"> · {detail.reports[0].reporter_relation}</span>}</p>
          )}
          <Matches c={c} suggestions={suggestions} lookup={lookup} canDecide={can("merge.decide")}
                   onDone={(kept) => { onChanged(); load(); if (kept && kept !== c.id) onSelect(kept); }} />
          {can("merge.decide") && <ManualMerge c={c} onDone={(kept) => { onChanged(); load(); if (kept !== c.id) onSelect(kept); }} />}
        </Fold>
        <Fold title="Activity history" icon={History} open={opened.has("Activity history")} onToggle={() => toggle("Activity history")}
              hint={tl ? `${tl.events.length} events · ${evidenceCount ? `${evidenceCount} evidence ${evidenceCount === 1 ? "item" : "items"}` : "no evidence yet"} · the transcript and the audit trail` : undefined}>
          {tl && detail ? <Timeline events={tl.events} evidence={tl.evidence} reports={detail.reports} quote={quote} notes={notes}
                                    canUndo={can("merge.decide")} onChanged={() => { onChanged(); load(); }} />
                        : <p className="text-body text-ink-3">Loading…</p>}
          <p className="mt-3"><a className="text-body underline underline-offset-2" href={`/audit?case=${c.id}`}>Check nothing was changed — this case&rsquo;s full history</a></p>
        </Fold>
      </div>
      </div>
    </aside>
  );
}

"use client";

// The case drawer (PRD F-C2), titled with the PS's words: Assignment · Facts · Timeline & evidence · Audit.
// It re-reads the case whenever a live update changes it, and offers only the actions this role may take.

import { useCallback, useEffect, useRef, useState } from "react";

import { Facts } from "@/components/desk/Facts";
import { Timeline } from "@/components/desk/Timeline";
import { Because, Button, Chip, Priority, Section } from "@/components/ui";
import { api, type Case, type CaseDetail, type Evidence, type Me, type TimelineEvent } from "@/lib/api";

export type Picked = { lat: number; lng: number } | null;

export function Drawer({ c, me, focus, picking, picked, onPickStart, onPickEnd, onClose }: {
  c: Case; me: Me | null; focus?: string | null; picking: boolean; picked: Picked;
  onPickStart: () => void; onPickEnd: () => void; onClose: () => void;
}) {
  const can = (a: string) => !!me?.permissions.includes(a);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [tl, setTl] = useState<{ events: TimelineEvent[]; evidence: Evidence[] } | null>(null);
  const [quote, setQuote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const body = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    api<CaseDetail>(`/v1/cases/${c.id}`).then(setDetail).catch(() => {});
    api<{ events: TimelineEvent[]; evidence: Evidence[] }>(`/v1/cases/${c.id}/timeline`).then(setTl).catch(() => {});
  }, [c.id]);
  useEffect(load, [load, c.version, c.updated_at]);
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
    <aside className="fixed inset-0 z-40 flex flex-col bg-paper md:static md:h-full md:w-[460px] md:shrink-0 md:border-l md:border-line" aria-label={`Case ${c.public_id}`}>
      <div className="border-b border-line px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <p className="flex items-baseline gap-2">
            <Priority level={c.priority} />
            <span className="tabular text-xl font-semibold tracking-tight">{c.public_id}</span>
            <Chip tone="quiet">{c.status === "reported" ? "not checked yet" : c.status}</Chip>
          </p>
          <Button variant="quiet" size="sm" onClick={onClose}>Close</Button>
        </div>
        <p className="mt-1 text-sm">{c.summary}</p>
        {c.priority_reasons.length > 0 && <Because>{c.priority} · {c.priority_reasons.join(" · ")}</Because>}
        <div className="mt-3 flex flex-wrap gap-2">
          {c.status === "reported" && can("case.check") && (
            <Button size="sm" variant="primary" onClick={() => act(() => api(`/v1/cases/${c.id}/check`, { method: "POST", json: {} }))}>Check</Button>
          )}
          {can("case.move_pin") && !picking && <Button size="sm" onClick={onPickStart}>Move pin</Button>}
        </div>
        {picking && (
          <form className="mt-3 space-y-2 rounded-lg border border-line p-3 text-sm" onSubmit={(e) => { e.preventDefault(); savePin(new FormData(e.currentTarget)); }}>
            <p>{picked ? <>New pin at <span className="tabular">{picked.lat.toFixed(5)}, {picked.lng.toFixed(5)}</span> · a person placed it, so its circle is 50 m.</>
                       : "Click the map where the household is."}</p>
            {picked && <input name="reason" required minLength={3} placeholder="Why (logged), e.g. caller confirmed on phone" className="h-8 w-full rounded-md border border-line px-2" autoFocus />}
            <div className="flex gap-2">
              {picked && <Button size="sm" variant="primary" type="submit">Save pin</Button>}
              <Button size="sm" variant="quiet" type="button" onClick={onPickEnd}>Cancel</Button>
            </div>
          </form>
        )}
        {error && <p className="mt-2 rounded-md bg-wash px-2 py-1 text-xs">{error}</p>}
      </div>
      <div ref={body} className="flex-1 overflow-y-auto px-5">
        <div data-section="Assignment"><Section title="Assignment"><p className="text-sm text-ink-2">No team yet.</p></Section></div>
        <div data-section="Facts">
          <Section title="Facts">
            <Facts c={c} canEdit={can("case.edit")} onQuote={setQuote} onChanged={load} />
            {detail?.reports[0]?.reporter_phone_masked && (
              <p className="mt-2 text-sm"><span className="text-ink-3">Contact</span> <span className="tabular">{detail.reports[0].reporter_phone_masked}</span>
                {detail.reports[0].reporter_relation && detail.reports[0].reporter_relation !== "unknown" && <span className="text-ink-3"> · {detail.reports[0].reporter_relation}</span>}</p>
            )}
          </Section>
        </div>
        <div data-section="Timeline & evidence">
          <Section title="Timeline & evidence">
            {tl && detail ? <Timeline events={tl.events} evidence={tl.evidence} reports={detail.reports} quote={quote} />
                          : <p className="text-sm text-ink-3">Loading…</p>}
          </Section>
        </div>
        <div data-section="Audit">
          <Section title="Audit">
            <a className="text-sm underline underline-offset-2" href={`/audit?case=${c.id}`}>This case&rsquo;s raw events in the hash-chained log</a>
          </Section>
        </div>
      </div>
    </aside>
  );
}

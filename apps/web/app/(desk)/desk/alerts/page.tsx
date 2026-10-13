"use client";

// Alerts: every warning the desk raised for this incident. Open ones first (a team not heard from, or more urgent
// families than free teams), then the ones already dealt with and how. Acting on an alert happens on the case.

import { use, useEffect, useMemo, useState } from "react";

import { IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { Card, Empty, useNow, ago } from "@/components/ui";
import { api, type Escalation, listCases } from "@/lib/api";
import { withWords } from "@/lib/words";

type Alert = Escalation & { resolved_at: string | null; resolution: string | null };

function Row({ e, incident, ids, now }: { e: Alert; incident: string; ids: Map<number, string>; now: number }) {
  const state = e.status === "resolved" ? `Dealt with${e.resolution ? `: ${e.resolution}` : ""}`
    : e.status === "acked" ? `${e.acked_by_name ?? "An officer"} is on it` : "Nobody on it yet";
  return (
    <li className="grid grid-cols-1 gap-x-4 gap-y-1 px-4 py-3.5 md:grid-cols-[minmax(0,1fr)_14rem_8.5rem] md:items-center">
      <span className="min-w-0">
        <span className="block text-body font-medium leading-snug">{withWords(e.line)}</span>
        <span className="block text-small text-ink-3">
          {e.role === "incharge" ? "Sent up to the senior officer · " : ""}raised {ago(e.opened_at, now)}
        </span>
      </span>
      <span className={`text-small ${e.status === "open" ? "font-medium text-ink" : "text-ink-2"}`}>{state}</span>
      <span className="flex flex-wrap gap-1.5 md:justify-end">
        {e.case_ids.slice(0, 3).map((id) => (
          <a key={id} href={`/desk/${incident}?case=${ids.get(id) ?? id}`}
             className="tabular inline-flex min-h-9 items-center rounded-full border border-line px-3 text-small font-medium hover:bg-wash">
            Open {ids.get(id) ?? `#${id}`}
          </a>
        ))}
        {e.case_ids.length > 3 && <span className="self-center text-small text-ink-3">+{e.case_ids.length - 3} more</span>}
      </span>
    </li>
  );
}

export default function Alerts({ params }: { params: Promise<{ incident: string }> }) {
  const { incident } = use(params);
  const me = useMe();
  const now = useNow(30_000);
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [ids, setIds] = useState<Map<number, string>>(new Map());

  useEffect(() => {
    const load = () => api<Alert[]>(`/v1/escalations?incident=${encodeURIComponent(incident)}&open=false`).then(setAlerts).catch(() => setAlerts([]));
    load();
    listCases({ incident }).then(({ cases }) => setIds(new Map(cases.map((c) => [c.id, c.public_id])))).catch(() => {});
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [incident]);

  const [open, done] = useMemo(() => {
    const all = alerts ?? [];
    return [all.filter((a) => a.status !== "resolved"),
            all.filter((a) => a.status === "resolved").sort((a, b) => (b.resolved_at ?? "").localeCompare(a.resolved_at ?? ""))];
  }, [alerts]);

  return (
    <IncidentPage me={me} code={incident} title="Alerts" sub="teams with contact overdue, and too few free teams">
      <h2 className="text-heading font-semibold">Open <span className="tabular font-normal text-ink-3">{open.length}</span></h2>
      <Card className="mt-2 overflow-hidden">
        {!alerts ? <Empty>Loading…</Empty> : open.length === 0 ? <Empty>No open alerts. Every team has checked in.</Empty> : (
          <ul className="divide-y divide-line">{open.map((e) => <Row key={e.id} e={e} incident={incident} ids={ids} now={now} />)}</ul>
        )}
      </Card>
      {done.length > 0 && (
        <>
          <h2 className="mt-8 text-heading font-semibold">Dealt with <span className="tabular font-normal text-ink-3">{done.length}</span></h2>
          <Card className="mt-2 overflow-hidden">
            <ul className="divide-y divide-line">{done.slice(0, 50).map((e) => <Row key={e.id} e={e} incident={incident} ids={ids} now={now} />)}</ul>
          </Card>
        </>
      )}
    </IncidentPage>
  );
}

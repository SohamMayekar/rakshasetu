"use client";

// Cases: every family reported on this desk, newest first. Filter by where they stand (waiting, a team on it,
// rescued, closed) and search by place, case number or what was said. A row opens the case on the desk.

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Filters, IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { Card, Empty, Priority, PriorityWell, useNow, ago } from "@/components/ui";
import { type Case, listCases } from "@/lib/api";

type Group = "all" | "waiting" | "team" | "rescued" | "closed";
const GROUP_OF: Record<string, Group> = {
  reported: "waiting", checked: "waiting", assigned: "team", acknowledged: "team", reached: "team",
  rescued: "rescued", closed: "closed", cancelled: "closed",
};
const STATUS: Record<string, string> = {
  reported: "Waiting · not checked yet", checked: "Waiting for a team", assigned: "Team sent", acknowledged: "Team accepted",
  reached: "Team reached them", rescued: "Rescued", closed: "Closed", cancelled: "Cancelled",
};
const PAGE = 100;

export default function Cases() {
  const me = useMe();
  const now = useNow(30_000);
  const [cases, setCases] = useState<Case[] | null>(null);
  const [group, setGroup] = useState<Group>("all");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    const load = () => listCases({}).then(({ cases }) => setCases(cases.filter((c) => c.status !== "merged"))).catch(() => {});
    load();
    const t = setInterval(load, 10_000);
    return () => clearInterval(t);
  }, []);

  const counts = useMemo(() => {
    const n: Record<Group, number> = { all: 0, waiting: 0, team: 0, rescued: 0, closed: 0 };
    for (const c of cases ?? []) { n.all++; n[GROUP_OF[c.status] ?? "waiting"]++; }
    return n;
  }, [cases]);
  const shown = useMemo(() => {
    const words = q.trim().toLowerCase();
    return (cases ?? [])
      .filter((c) => group === "all" || GROUP_OF[c.status] === group)
      .filter((c) => !words || [c.public_id, c.location_text, c.summary].some((v) => v?.toLowerCase().includes(words)))
      .sort((a, b) => b.created_at.localeCompare(a.created_at));
  }, [cases, group, q]);

  return (
    <IncidentPage me={me} title="Cases" sub="every family reported, newest first">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Filters value={group} onChange={(g) => { setGroup(g); setLimit(PAGE); }} items={[
          { key: "all", label: "All", count: counts.all }, { key: "waiting", label: "Waiting", count: counts.waiting },
          { key: "team", label: "Team on it", count: counts.team }, { key: "rescued", label: "Rescued", count: counts.rescued },
          { key: "closed", label: "Closed", count: counts.closed }]} />
        <label className="relative block md:w-72">
          <span className="sr-only">Search cases</span>
          <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Place, case number or words…"
                 autoComplete="off" spellCheck={false}
                 className="field !rounded-full !pl-10 !pr-4 !h-10" />
        </label>
      </div>

      <Card className="mt-3 overflow-hidden">
        {!cases ? <Empty>Loading…</Empty> : shown.length === 0 ? <Empty>No cases match.</Empty> : (
          <ul className="divide-y divide-line">
            {shown.slice(0, limit).map((c) => (
              <li key={c.id}>
                <a href={`/desk?case=${c.public_id}`}
                   className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-0.5 px-4 py-3 transition-colors hover:bg-wash md:grid-cols-[auto_7rem_minmax(0,1fr)_12rem_6.5rem]">
                  <PriorityWell level={c.priority} />
                  <span className="min-w-0 md:contents">
                    <span className="flex items-baseline gap-2 md:block">
                      <span className="tabular block font-semibold">{c.public_id}</span>
                      <span className="block text-small"><Priority level={c.priority} shape={false} /></span>
                    </span>
                    <span className="block min-w-0">
                      <span className="block truncate font-medium">{c.location_text ?? "Place not known yet"}</span>
                      <span className="block truncate text-small text-ink-2">{c.summary ?? "—"}</span>
                    </span>
                    <span className="flex gap-2 text-small md:contents">
                      <span className="block text-ink-2 md:text-body md:text-ink">{STATUS[c.status] ?? c.status}</span>
                      <span className="tabular block text-ink-3 md:text-right">{ago(c.updated_at, now)}</span>
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        )}
        {shown.length > limit && (
          <div className="border-t border-line p-3 text-center">
            <button onClick={() => setLimit(limit + PAGE)} className="min-h-11 text-body underline underline-offset-4">
              Show {Math.min(PAGE, shown.length - limit)} more of {shown.length - limit}
            </button>
          </div>
        )}
      </Card>
    </IncidentPage>
  );
}

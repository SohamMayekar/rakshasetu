"use client";

// Teams: every rescue team on this desk and where it stands. Contact overdue first (they need a radio call), then
// busy, free and out of service. A team's "last heard" is real contact only (a tap or a radio call), never the
// app merely being open.

import { Radio, Smartphone } from "lucide-react";
import { use, useEffect, useMemo, useState } from "react";

import { Filters, IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { Card, Chip, Empty, useNow, ago } from "@/components/ui";
import { api } from "@/lib/api";

type Team = { id: number; name: string; agency: string; capabilities: string[]; has_app: boolean; radio_channel: string | null;
              status: "available" | "assigned" | "overdue" | "out_of_service"; status_reason: string | null; max_active: number;
              last_contact_at: string | null; last_seen_at: string | null; district: string; active: number; standdowns_owed: number };
type Group = "all" | "quiet" | "busy" | "free" | "out";

const groupOf = (t: Team): Exclude<Group, "all"> =>
  t.status === "out_of_service" ? "out" : t.status === "overdue" || t.standdowns_owed > 0 ? "quiet" : t.active > 0 ? "busy" : "free";
const ORDER: Exclude<Group, "all">[] = ["quiet", "busy", "free", "out"];
const STATE: Record<Exclude<Group, "all">, string> = { quiet: "Contact overdue", busy: "Busy", free: "Free", out: "Out of service" };

export default function Teams({ params }: { params: Promise<{ incident: string }> }) {
  const { incident } = use(params);
  const me = useMe();
  const now = useNow(30_000);
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [group, setGroup] = useState<Group>("all");

  useEffect(() => {
    const load = () => api<Team[]>(`/v1/teams?incident=${encodeURIComponent(incident)}`).then(setTeams).catch(() => setTeams([]));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [incident]);

  const counts = useMemo(() => {
    const n: Record<Group, number> = { all: 0, quiet: 0, busy: 0, free: 0, out: 0 };
    for (const t of teams ?? []) { n.all++; n[groupOf(t)]++; }
    return n;
  }, [teams]);
  const shown = (teams ?? []).filter((t) => group === "all" || groupOf(t) === group)
    .sort((a, b) => ORDER.indexOf(groupOf(a)) - ORDER.indexOf(groupOf(b)) || a.name.localeCompare(b.name));

  return (
    <IncidentPage me={me} code={incident} title="Teams" sub="who can go, who is busy, whose check-in is overdue">
      <Filters value={group} onChange={setGroup} items={[
        { key: "all", label: "All", count: counts.all }, { key: "quiet", label: "Contact overdue", count: counts.quiet },
        { key: "busy", label: "Busy", count: counts.busy }, { key: "free", label: "Free", count: counts.free },
        { key: "out", label: "Out of service", count: counts.out }]} />

      <Card className="mt-3 overflow-hidden">
        {!teams ? <Empty>Loading…</Empty> : shown.length === 0 ? <Empty>No teams here.</Empty> : (
          <ul className="divide-y divide-line">
            {shown.map((t) => {
              const g = groupOf(t);
              const How = t.has_app ? Smartphone : Radio;
              return (
                <li key={t.id} className={`grid grid-cols-[minmax(0,1fr)_auto] items-start md:items-center gap-x-4 gap-y-1 px-4 py-3.5 md:grid-cols-[minmax(0,1fr)_11rem_7rem_10rem] ${g === "out" ? "stale" : ""}`}>
                  <span className="min-w-0">
                    <span className="block font-semibold md:truncate">{t.name}</span>
                    <span className="block text-small text-ink-2 md:truncate">
                      <How className="mr-1.5 inline size-3.5 align-[-2px] text-ink-3" strokeWidth={1.8} aria-hidden />
                      {t.has_app ? "Team app" : t.radio_channel === "phone" ? "Phone calls only" : `Radio only${t.radio_channel ? ` (${t.radio_channel})` : ""}`}
                      {t.capabilities.length > 0 && <> · {t.capabilities.slice(0, 3).join(", ")}</>} · {t.district}
                    </span>
                  </span>
                  <span className="justify-self-end md:justify-self-start">
                    {g === "quiet" ? <Chip tone="attention">{t.standdowns_owed > 0 && t.status !== "overdue" ? "tell them: case moved" : "contact overdue"}</Chip>
                      : <span className="text-body">{STATE[g]}{g === "out" && t.status_reason ? `: ${t.status_reason}` : ""}</span>}
                  </span>
                  <span className="tabular text-small text-ink-2 md:text-body md:text-ink">
                    {t.active} of {t.max_active} {t.max_active === 1 ? "case" : "cases"}
                  </span>
                  <span className="tabular text-small text-ink-3 md:text-right">
                    {t.last_contact_at ? `last contact ${ago(t.last_contact_at, now)}` : "no contact yet"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </IncidentPage>
  );
}

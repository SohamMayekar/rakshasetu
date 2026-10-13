"use client";

// Teams: every rescue team on this desk and where it stands. The first line is a readable name built from the
// team's own data (agency · capability · base district); the official name stays under it for traceability.
// Contact overdue first (they need a radio call), then responding, available and out of service. A team's
// "last contact" is real contact only (a tap or a radio call), never the app merely being open.

import { Plus, Radio, Smartphone } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Filters, IncidentPage, useMe } from "@/components/desk/IncidentPage";
import { NewTeam } from "@/components/desk/NewTeam";
import { Button, Card, Chip, Empty, useNow, ago } from "@/components/ui";
import { api } from "@/lib/api";
import { availability, teamLabel } from "@/lib/words";

type Team = { id: number; name: string; agency: string; capabilities: string[]; has_app: boolean; radio_channel: string | null;
              status: "available" | "assigned" | "overdue" | "out_of_service"; status_reason: string | null; max_active: number;
              last_contact_at: string | null; last_seen_at: string | null; district: string; active: number; standdowns_owed: number };
type Group = "all" | "quiet" | "busy" | "free" | "out";

const groupOf = (t: Team): Exclude<Group, "all"> =>
  t.status === "out_of_service" ? "out" : t.status === "overdue" || t.standdowns_owed > 0 ? "quiet" : t.active > 0 ? "busy" : "free";
const ORDER: Exclude<Group, "all">[] = ["quiet", "busy", "free", "out"];

export default function Teams() {
  const me = useMe();
  const now = useNow(30_000);
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [group, setGroup] = useState<Group>("all");
  const [adding, setAdding] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const admin = !!me?.permissions.includes("incident.admin");
  const load = useCallback(() => { api<Team[]>("/v1/teams").then(setTeams).catch(() => setTeams([])); }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const counts = useMemo(() => {
    const n: Record<Group, number> = { all: 0, quiet: 0, busy: 0, free: 0, out: 0 };
    for (const t of teams ?? []) { n.all++; n[groupOf(t)]++; }
    return n;
  }, [teams]);
  const shown = (teams ?? []).filter((t) => group === "all" || groupOf(t) === group)
    .sort((a, b) => ORDER.indexOf(groupOf(a)) - ORDER.indexOf(groupOf(b)) || a.name.localeCompare(b.name));

  return (
    <IncidentPage me={me} title="Teams" sub="who can go, who is busy, whose check-in is overdue"
                  aside={admin ? <Button variant="primary" onClick={() => { setAdding((a) => !a); setNote(null); }}><Plus className="size-4" aria-hidden />Add a team</Button> : undefined}>
      {adding && admin && (
        <Card className="mb-4">
          <h2 className="border-b border-line px-4 py-3 text-heading font-semibold">Add a team</h2>
          <NewTeam me={me} onCreated={(n) => { setAdding(false); setNote(n); load(); }} />
        </Card>
      )}
      {note && <p role="status" className="mb-4 rounded-xl bg-wash px-4 py-3 text-body">{note}</p>}
      <Filters value={group} onChange={setGroup} items={[
        { key: "all", label: "All", count: counts.all }, { key: "quiet", label: "Check-in overdue", count: counts.quiet },
        { key: "busy", label: "Responding", count: counts.busy }, { key: "free", label: "Available", count: counts.free },
        { key: "out", label: "Out of service", count: counts.out }]} />

      <Card className="mt-3 overflow-hidden">
        {!teams ? <Empty>Loading…</Empty> : shown.length === 0 ? <Empty>{teams.length === 0 ? (admin ? "No teams yet. Add the first one with “Add a team”." : "No teams yet. The national admin adds them.") : "No teams here."}</Empty> : (
          <ul className="divide-y divide-line">
            {shown.map((t) => {
              const g = groupOf(t);
              const How = t.has_app ? Smartphone : Radio;
              const label = teamLabel(t) || t.name;
              return (
                <li key={t.id} className={`grid grid-cols-[minmax(0,1fr)_auto] items-start md:items-center gap-x-4 gap-y-1 px-4 py-3.5 md:grid-cols-[minmax(0,1fr)_11rem_7rem_10rem] ${g === "out" ? "stale" : ""}`}>
                  <span className="min-w-0">
                    <span className="block font-semibold md:truncate">{label}</span>
                    <span className="block text-small text-ink-2 md:truncate">
                      <How className="mr-1.5 inline size-3.5 align-[-2px] text-ink-3" strokeWidth={1.8} aria-hidden />
                      {t.has_app ? "Team app" : t.radio_channel === "phone" ? "Phone calls only" : `Radio only${t.radio_channel ? ` (${t.radio_channel})` : ""}`}
                      {" · "}{t.name}
                      {t.capabilities.length === 0 && <> · capability unknown</>}
                    </span>
                  </span>
                  <span className="justify-self-end md:justify-self-start">
                    {g === "quiet" ? <Chip tone="attention">{t.standdowns_owed > 0 && t.status !== "overdue" ? "tell them: case moved" : "check-in overdue"}</Chip>
                      : <span className="text-body">{availability(t.status)}{g === "out" && t.status_reason ? `: ${t.status_reason}` : ""}</span>}
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

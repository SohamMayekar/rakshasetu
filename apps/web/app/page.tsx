"use client";

// The front door and the Incidents screen (PRD F-C1).
// Signed out: two big choices only, "I need help" (the reporter page) and "Control room dashboard" (sign in), with
// the rescue team's app as a small link (m64). Signed in: each person goes to their own screen (the duty officer
// to their desk, a team to its app); whoever sees several incidents gets this screen, one card per incident with
// its three numbers (families waiting, with a team, rescued) and a map of India: a national layer of district desks.

import { ArrowRight, LayoutDashboard, type LucideIcon, Mic, Mountain, Waves, Wind } from "lucide-react";
import { useEffect, useState } from "react";

import { IncidentsMap } from "@/components/IncidentsMap";
import { AppShell, Page } from "@/components/shell/AppShell";
import { Mark } from "@/components/shell/Sidebar";
import { waitingFamilies } from "@/components/desk/Today";
import { Card, Chip, IconWell, PageHeader } from "@/components/ui";
import type { Queue } from "@/lib/queue";
import type { Promises } from "@/lib/api";
import { api, ApiError, type Me } from "@/lib/api";

type Incident = { id: number; code: string; name: string; type: string; states: string[]; status: string; lat: number; lng: number;
                  districts: string[]; promises: Promises | null };

const STATUS: Record<string, string> = { active: "Active", draft: "Draft", standing_down: "Standing down", closed: "Closed" };

const KIND_ICON: Record<string, LucideIcon> = { flood: Waves, cyclone: Wind, landslide: Mountain };

// One incident's three numbers, in the desk's words: families waiting for a person, with a team, rescued or closed.
// Ink only when lives are at risk (an urgent family without a team, a team not heard from).
function Numbers({ q, p }: { q: Queue | null; p: Promises | null }) {
  const cell = (label: string, value: number | null, warn?: string | false) => (
    <div className="min-w-0 rounded-2xl bg-wash px-3 py-2.5">
      <p className="text-xs text-ink-2">{label}</p>
      <p className="tabular text-xl font-semibold">{value ?? "–"}</p>
      {warn && <p className="mt-0.5 inline-block rounded-md bg-ink px-1.5 text-xs font-medium text-paper">{warn}</p>}
    </div>
  );
  const unowned = p?.stale.p1_unowned ?? 0, quiet = p?.stale.overdue ?? 0;
  return (
    <div className="mt-4 grid grid-cols-3 gap-2">
      {cell("Need help now", q ? waitingFamilies(q) : null, unowned > 0 && `${unowned} urgent without a team`)}
      {cell("Team on it", q?.on_it ?? null, quiet > 0 && `${quiet} not heard from`)}
      {cell("Rescued or closed", q ? q.rescued_closing + q.closed : null)}
    </div>
  );
}

const DESK_ROLES = ["call_taker", "duty_officer", "incharge", "admin"];

// Two big choices, nothing else competing: who are you? (Works from 320 px phones to the projector.)
function FrontDoor() {
  const choice = "group flex flex-col items-start gap-4 rounded-card border border-line/80 bg-paper p-6 text-left shadow-[var(--shadow-card)] transition-colors hover:bg-wash md:p-8";
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-3xl">
        <p className="flex items-center justify-center gap-2.5 text-ink"><Mark className="size-9" /><span className="text-2xl font-semibold tracking-tight">RakshaSetu</span></p>
        <h1 className="mt-4 text-center text-display font-semibold leading-tight tracking-tight ">Get every family to safety.</h1>
        <p className="mx-auto mt-2 max-w-xl text-center text-ink-2">In a flood, every call for help reaches the control room once, gets one rescue team, and is followed until the family is safe.</p>
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <a href="/r" className={choice}>
            <IconWell icon={Mic} size="lg" tone="ink" />
            <span>
              <span className="block text-2xl font-semibold tracking-tight">I need help</span>
              <span className="mt-1 block text-ink-2">The phone app for people in danger and their families. Speak or type. Nothing to remember.</span>
            </span>
            <span className="mt-auto inline-flex h-11 items-center gap-1.5 rounded-full bg-ink px-5 font-medium text-paper">Ask for help<ArrowRight className="size-4" aria-hidden /></span>
          </a>
          <a href="/login" className={choice}>
            <IconWell icon={LayoutDashboard} size="lg" />
            <span>
              <span className="block text-2xl font-semibold tracking-tight">Control room dashboard</span>
              <span className="mt-1 block text-ink-2">For the district duty officer: every request on one screen, each family with one owner.</span>
            </span>
            <span className="mt-auto inline-flex h-11 items-center gap-1.5 rounded-full border border-ink px-5 font-medium">Sign in<ArrowRight className="size-4" aria-hidden /></span>
          </a>
        </div>
        <p className="mt-6 text-center text-sm text-ink-2">Rescue team? <a href="/responder" className="font-medium text-ink underline underline-offset-4">Open the team app</a></p>
        <p className="mt-8 text-center text-xs text-ink-3">A demo: every person and phone number in it is made up.</p>
      </div>
    </main>
  );
}


export default function Incidents() {
  const [me, setMe] = useState<Me | null>(null);
  const [list, setList] = useState<Incident[] | null>(null);
  const [out, setOut] = useState(false);
  const [queues, setQueues] = useState<Record<string, Queue>>({});

  useEffect(() => {
    api<Me>("/v1/me").then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) setOut(true); });
    const load = () => api<Incident[]>("/v1/incidents").then((l) => {
      setList(l);
      for (const i of l) api<Queue>(`/v1/queue?incident=${i.code}`).then((q) => setQueues((m) => ({ ...m, [i.code]: q }))).catch(() => {});
    }).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const home = me && (me.user.role === "team_lead" ? "/responder"
    : DESK_ROLES.includes(me.user.role) && me.incidents.length === 1 ? `/desk/${me.incidents[0].code}` : null);
  useEffect(() => { if (home) location.replace(home); }, [home]);

  if (out) return <FrontDoor />;
  if (home) return null;
  const desk = me && DESK_ROLES.includes(me.user.role);
  const go = (code: string) => { if (desk) location.href = `/desk/${code}`; };
  return (
    <AppShell me={me}>
      <Page wide>
        <PageHeader title="All incidents" sub="Each disaster has its own control room. Open one to start helping." />
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
          <section className="space-y-4" aria-label="Incidents">
            {(list ?? []).map((i) => {
              const Icon = KIND_ICON[i.type] ?? Waves;
              return (
                <Card as="article" key={i.id} className="p-5">
                  <div className="flex items-start gap-3">
                    <IconWell icon={Icon} size="lg" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-3">
                        <h2 className="text-lg font-semibold leading-snug tracking-tight">{i.name}</h2>
                        {i.status !== "active" && <Chip tone="neutral">{STATUS[i.status] ?? i.status}</Chip>}
                      </div>
                      <p className="text-sm text-ink-2">{i.states.join(", ")} · {i.districts.join(" · ")}</p>
                    </div>
                  </div>
                  <Numbers q={queues[i.code] ?? null} p={i.promises} />
                  {desk && (
                    <a href={`/desk/${i.code}`} className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-full bg-ink px-4 text-sm font-medium text-paper hover:bg-[#2b2b2b]">
                      Open the control room<ArrowRight className="size-4" aria-hidden />
                    </a>
                  )}
                </Card>
              );
            })}
          </section>
          <Card className="min-h-80 overflow-hidden lg:sticky lg:top-6 lg:h-[calc(100vh-9rem)]">
            {list && <IncidentsMap pins={list.filter((i) => i.lat != null).map((i) => ({ code: i.code, name: i.name, lat: i.lat, lng: i.lng,
                                                                                           broken: !!i.promises && (i.promises.stale.p1_unowned > 0 || i.promises.stale.overdue > 0) }))}
                                   onOpen={go} />}
          </Card>
        </div>
      </Page>
    </AppShell>
  );
}

"use client";

// The front door and the Incidents screen (PRD F-C1).
// Signed out: two big choices only, "I need help" (the reporter page) and "Control room dashboard" (sign in), with
// the rescue team's app as a small link (m64). Signed in: each person goes to their own screen (the duty officer
// to their desk, a team to its app); whoever sees several incidents gets this screen, one card per incident with
// its own promise bar and a map of India: "a national layer of district desks".

import { ArrowRight, CalendarDays, CopyCheck, Inbox, LayoutDashboard, type LucideIcon, Mic, Mountain, Timer, Waves, Wind } from "lucide-react";
import { useEffect, useState } from "react";

import { IncidentsMap } from "@/components/IncidentsMap";
import { AppShell, Page } from "@/components/shell/AppShell";
import { Mark } from "@/components/shell/Sidebar";
import { Card, Chip, IconWell, PageHeader, Pill } from "@/components/ui";
import type { Promises } from "@/components/desk/PromiseBar";
import { api, ApiError, type Me } from "@/lib/api";

type Incident = { id: number; code: string; name: string; type: string; states: string[]; status: string; lat: number; lng: number;
                  districts: string[]; promises: Promises | null };

const STATUS: Record<string, string> = { active: "Active", draft: "Draft", standing_down: "Standing down", closed: "Closed" };

const KIND_ICON: Record<string, LucideIcon> = { flood: Waves, cyclone: Wind, landslide: Mountain };

function Line({ icon: Icon, name, children }: { icon: LucideIcon; name: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-ink-3" strokeWidth={1.8} aria-hidden />
      <p className="min-w-0"><span className="text-ink-3">{name} · </span>{children}</p>
    </div>
  );
}

function Bar({ p }: { p: Promises }) {
  const n = (v: number, broken = false) => <b className={`tabular ${broken ? "rounded-md bg-ink px-1.5 text-paper" : ""}`}>{v}</b>;
  return (
    <div className="mt-4 space-y-2 rounded-2xl bg-wash px-4 py-3 text-sm">
      <Line icon={Inbox} name="Never lost">{n(p.lost.reports)} reports = {n(p.lost.cases)} cases + {n(p.lost.merged)} merged + {n(p.lost.to_check)} to check + {n(p.lost.without_home, p.lost.broken)} without a home</Line>
      <Line icon={CopyCheck} name="Never doubled">{n(p.doubled.merged)} merged · {n(p.doubled.to_check, p.doubled.broken)} to check · {n(p.doubled.refused)} refused</Line>
      <Line icon={Timer} name="Never stale">{n(p.stale.p1_unowned, p.stale.p1_unowned > 0)} P1 without owner &gt; 5 min · {n(p.stale.overdue, p.stale.overdue > 0)} contact overdue</Line>
    </div>
  );
}

const DESK_ROLES = ["call_taker", "duty_officer", "incharge", "admin"];

// Two big choices, nothing else competing: who are you? (Works from 320 px phones to the projector.)
function FrontDoor() {
  const choice = "group flex flex-col items-start gap-4 rounded-[28px] border border-line/80 bg-paper p-6 text-left shadow-[var(--shadow-card)] transition-colors hover:bg-wash md:p-8";
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-3xl">
        <p className="flex items-center justify-center gap-2.5 text-ink"><Mark className="size-9" /><span className="text-2xl font-semibold tracking-tight">RakshaSetu</span></p>
        <h1 className="mt-4 text-center text-[26px] font-semibold leading-tight tracking-tight md:text-[32px]">Never lost. Never doubled. Never stale.</h1>
        <p className="mx-auto mt-2 max-w-xl text-center text-ink-2">Rescue requests in a flood: every family becomes one case with one rescue team, until they are safe.</p>
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

function greeting(now: Date) {
  const h = Number(now.toLocaleString("en-IN", { hour: "numeric", hour12: false, timeZone: "Asia/Kolkata" }));
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function Incidents() {
  const [me, setMe] = useState<Me | null>(null);
  const [list, setList] = useState<Incident[] | null>(null);
  const [out, setOut] = useState(false);
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    api<Me>("/v1/me").then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) setOut(true); });
    const load = () => api<Incident[]>("/v1/incidents").then(setList).catch(() => {});
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
  const live = (list ?? []).filter((i) => i.status === "active").length;
  return (
    <AppShell me={me}>
      <Page wide>
        <PageHeader
          title={me && now ? `${greeting(now)}, ${me.user.name}` : "Incidents"}
          sub={list ? `${live} live incident${live === 1 ? "" : "s"}, each a district desk with its own three promises.` : " "}
          aside={now && <Pill icon={CalendarDays}><span className="tabular">{now.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" })}</span></Pill>} />
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
                        <h2 className="text-lg font-semibold leading-snug tracking-tight">{i.name} <span className="tabular font-normal text-ink-3">{i.code}</span></h2>
                        <Chip tone="neutral">{STATUS[i.status] ?? i.status}</Chip>
                      </div>
                      <p className="text-sm text-ink-2">{i.states.join(", ")} · {i.districts.join(" · ")}</p>
                    </div>
                  </div>
                  {i.promises && <Bar p={i.promises} />}
                  {desk && (
                    <a href={`/desk/${i.code}`} className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-full bg-ink px-4 text-sm font-medium text-paper hover:bg-[#2b2b2b]">
                      Open the desk<ArrowRight className="size-4" aria-hidden />
                    </a>
                  )}
                </Card>
              );
            })}
            {me?.user.role === "seoc_viewer" && <p className="px-1 text-xs text-ink-3">The SEOC sees totals and capacity requests; the district desks act.</p>}
          </section>
          <Card className="min-h-80 overflow-hidden lg:sticky lg:top-6 lg:h-[calc(100vh-9rem)]">
            {list && <IncidentsMap pins={list.filter((i) => i.lat != null).map((i) => ({ code: i.code, name: i.name, lat: i.lat, lng: i.lng,
                                                                                           broken: !!i.promises && (i.promises.stale.broken || i.promises.lost.broken || i.promises.doubled.broken) }))}
                                   onOpen={go} />}
          </Card>
        </div>
      </Page>
    </AppShell>
  );
}

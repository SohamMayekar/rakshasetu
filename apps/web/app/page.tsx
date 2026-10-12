"use client";

// The Incidents screen (PRD F-C1): one card per live incident, each with its own promise bar, and a map of India.
// "A national layer of district desks": one click opens an incident's desk; the SEOC viewer sees totals only.

import { ArrowRight, CalendarDays, CopyCheck, Inbox, type LucideIcon, Mountain, Timer, Waves, Wind } from "lucide-react";
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

  if (out) {
    return (
      <main className="grid min-h-screen place-items-center bg-canvas px-4">
        <Card className="w-full max-w-md p-8 text-center">
          <Mark className="mx-auto size-12 text-ink" />
          <h1 className="mt-4 text-3xl font-semibold tracking-tight">RakshaSetu</h1>
          <p className="mt-2 text-ink-2">Never lost. Never doubled. Never stale.</p>
          <a className="mt-6 inline-flex h-10 items-center rounded-full bg-ink px-6 text-sm font-medium text-paper" href="/login">Sign in</a>
        </Card>
      </main>
    );
  }
  const desk = me && ["call_taker", "duty_officer", "incharge", "admin"].includes(me.user.role);
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

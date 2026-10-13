"use client";

// The landing page, the front door and the Incidents screen (PRD F-C1).
// Signed out: the public landing page (components/landing). The two big choices — "I need help" (the reporter
// page) and "Control room dashboard" (sign in), with the rescue team's app as a small link (m64) — still answer
// at /?door=1. Signed in: each person goes to their own screen (the duty officer
// to their desk, a team to its app); whoever sees several incidents gets this screen, one card per incident with
// its three numbers (families waiting, with a team, rescued) and a map of India: a national layer of district desks.

import { ArrowRight, Building2, Car, Flame, HelpingHand, LayoutDashboard, type LucideIcon, Mic, Mountain, Siren, Waves, Wind } from "lucide-react";
import { useEffect, useState } from "react";

import { IncidentsMap } from "@/components/IncidentsMap";
import Landing from "@/components/landing/Landing";
import { AppShell, Page } from "@/components/shell/AppShell";
import { Mark } from "@/components/shell/Sidebar";
import { waitingFamilies } from "@/components/desk/Today";
import { Card, Chip, IconWell, PageHeader } from "@/components/ui";
import type { Queue } from "@/lib/queue";
import type { Promises } from "@/lib/api";
import { api, ApiError, type Me } from "@/lib/api";
import { enterNationalDesk } from "@/lib/enter";

type Incident = { id: number; code: string; name: string; type: string; states: string[]; status: string; lat: number; lng: number;
                  districts: string[]; promises: Promises | null };

const STATUS: Record<string, string> = { active: "Active", draft: "Draft", standing_down: "Standing down", closed: "Closed" };

const KIND_ICON: Record<string, LucideIcon> = { flood: Waves, cyclone: Wind, landslide: Mountain, fire: Flame, collapse: Building2, accident: Car, other: Siren };

// One incident's three numbers, in the desk's words: families waiting for a person, with a team, rescued or closed.
// Ink only when lives are at risk (an urgent family without a team, a team not heard from).
function Numbers({ q, p }: { q: Queue | null; p: Promises | null }) {
  const cell = (label: string, value: number | null, warn?: string | false) => (
    <div className="min-w-0 rounded-2xl bg-wash px-3 py-2.5">
      <p className="text-small text-ink-2">{label}</p>
      <p className="tabular text-xl font-semibold">{value ?? "–"}</p>
      {warn && <p className="mt-0.5 inline-block rounded-md bg-ink px-1.5 text-small font-medium text-paper">{warn}</p>}
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
function FrontDoor({ me }: { me?: Me | null }) {
  const choice = "group flex flex-col items-start gap-4 rounded-card border border-line/80 bg-paper p-6 text-left shadow-[var(--shadow-card)] transition-colors hover:bg-wash md:p-8 disabled:opacity-60";
  const deskUrl = !me ? "/login" : me.user.role === "team_lead" ? "/responder" : DESK_ROLES.includes(me.user.role) ? "/desk" : "/?incidents";
  const [busy, setBusy] = useState(false);
  // One tap into the control room: on the demo listener the duty officer's profile in config signs in with no
  // password (the same mechanism the old picker used). Anywhere else (or if that fails) it asks for a password.
  const enterDesk = async () => {
    if (me) { location.href = deskUrl; return; }
    setBusy(true);
    await enterNationalDesk();
  };
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center bg-canvas px-4 py-10">
      <div className="w-full max-w-3xl">
        {me && (
          <div className="mb-6 flex items-center justify-between rounded-2xl border border-line bg-paper p-4 shadow-sm">
            <div>
              <p className="text-small text-ink-2">Active Session</p>
              <p className="text-body font-semibold text-ink">{me.user.name} · {me.user.role_label}</p>
            </div>
            <div className="flex items-center gap-3">
              <a href={deskUrl} className="inline-flex h-9 items-center rounded-full bg-ink px-4 text-small font-medium text-paper hover:bg-[#2b2b2b]">
                {me && me.user.role === "team_lead" ? "Open the team app →" : "Open Control Room →"}
              </a>
              <button
                type="button"
                onClick={() => {
                  fetch("/v1/auth/logout", { method: "POST" }).then(() => {
                    location.href = "/";
                  });
                }}
                className="text-small font-medium text-ink-2 hover:text-ink underline"
              >
                Sign out
              </button>
            </div>
          </div>
        )}
        <p className="flex items-center justify-center gap-2.5 text-ink"><Mark className="size-9" /><span className="text-2xl font-semibold tracking-tight">RakshaSetu</span></p>
        <h1 className="mt-4 text-center text-display font-semibold leading-tight tracking-tight ">One command view for every emergency.</h1>
        <p className="mx-auto mt-2 max-w-xl text-center text-ink-2">Every call for help — flood, cyclone, fire, collapse, accident — reaches the control room once, gets one response team, and is followed until people are safe.</p>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <a href="/r" className={choice}>
            <IconWell icon={Mic} size="lg" tone="ink" />
            <span>
              <span className="block whitespace-nowrap text-xl font-semibold tracking-tight">I need help</span>
              <span className="mt-1 block text-ink-2">For people in danger and their families. Speak or type; nothing to remember.</span>
            </span>
            <span className="mt-auto inline-flex h-11 items-center gap-1.5 whitespace-nowrap rounded-full bg-ink px-5 font-medium text-paper">Ask for help<ArrowRight className="size-4" aria-hidden /></span>
          </a>
          <a href="/responder" className={choice}>
            <IconWell icon={HelpingHand} size="lg" />
            <span>
              <span className="block whitespace-nowrap text-xl font-semibold tracking-tight">I am a volunteer</span>
              <span className="mt-1 block text-ink-2">The rescue team&rsquo;s phone app: pick your team, accept a case, record who you took out.</span>
            </span>
            <span className="mt-auto inline-flex h-11 items-center gap-1.5 whitespace-nowrap rounded-full border border-ink px-5 font-medium">Open team app<ArrowRight className="size-4" aria-hidden /></span>
          </a>
          <button type="button" onClick={enterDesk} disabled={busy} className={choice}>
            <IconWell icon={LayoutDashboard} size="lg" />
            <span>
              <span className="block whitespace-nowrap text-xl font-semibold tracking-tight">I am an admin</span>
              <span className="mt-1 block text-ink-2">The control room: one universal desk for every request and every team.</span>
            </span>
            <span className="mt-auto inline-flex h-11 items-center gap-1.5 whitespace-nowrap rounded-full border border-ink px-5 font-medium">
              {busy ? "Opening…" : me ? "Open the desk" : "Sign in"}<ArrowRight className="size-4" aria-hidden />
            </span>
          </button>
        </div>
        <p className="mt-8 text-center text-small text-ink-3">A demo: every person and phone number in it is made up.</p>
      </div>
    </main>
  );
}


export default function Incidents() {
  const [me, setMe] = useState<Me | null>(null);
  const [list, setList] = useState<Incident[] | null>(null);
  const [out, setOut] = useState(true);
  const [door, setDoor] = useState(false);
  const [queues, setQueues] = useState<Record<string, Queue>>({});

  useEffect(() => {
    if (typeof window !== "undefined" && new URLSearchParams(window.location.search).has("door")) {
      setDoor(true);
    }
    api<Me>("/v1/me")
      .then((m) => {
        setMe(m);
        setOut(false);
      })
      .catch(() => {
        setOut(true);
      });
    const load = () => api<Incident[]>("/v1/incidents").then((l) => {
      setList(l);
      for (const i of l) api<Queue>(`/v1/queue?incident=${i.code}`).then((q) => setQueues((m) => ({ ...m, [i.code]: q }))).catch(() => {});
    }).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const appRedirect = typeof window !== "undefined" && new URLSearchParams(window.location.search).has("app");
  const home = appRedirect && me && !door && (me.user.role === "team_lead" ? "/responder"
    : DESK_ROLES.includes(me.user.role) ? "/desk" : null);
  useEffect(() => { if (home) location.replace(home); }, [home]);

  if (door) return <FrontDoor me={me} />;
  if (home) return null;
  const showIncidents = typeof window !== "undefined" && new URLSearchParams(window.location.search).has("incidents");
  if (showIncidents && me) {
    const desk = DESK_ROLES.includes(me.user.role);
    const go = () => { if (desk) location.href = "/desk"; };
    return (
      <AppShell me={me}>
        <Page wide>
          <PageHeader title="All incidents" sub="One national desk covers every disaster below. Open it to start helping." />
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
                        <p className="text-body text-ink-2">{i.states.join(", ")} · {i.districts.join(" · ")}</p>
                      </div>
                    </div>
                    <Numbers q={queues[i.code] ?? null} p={i.promises} />
                    {desk && (
                      <a href="/desk" className="mt-4 inline-flex h-9 items-center gap-1.5 rounded-full bg-ink px-4 text-body font-medium text-paper hover:bg-[#2b2b2b]">
                        Open the national desk<ArrowRight className="size-4" aria-hidden />
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

  return <Landing me={me} />;
}


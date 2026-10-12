"use client";

// The Incidents screen (PRD F-C1): one card per live incident, each with its own promise bar, and a map of India.
// "A national layer of district desks": one click opens an incident's desk; the SEOC viewer sees totals only.

import { useEffect, useState } from "react";

import { IncidentsMap } from "@/components/IncidentsMap";
import type { Promises } from "@/components/desk/PromiseBar";
import { api, ApiError, type Me } from "@/lib/api";

type Incident = { id: number; code: string; name: string; type: string; states: string[]; status: string; lat: number; lng: number;
                  districts: string[]; promises: Promises | null };

const STATUS: Record<string, string> = { active: "Active", draft: "Draft", standing_down: "Standing down", closed: "Closed" };

function Bar({ p }: { p: Promises }) {
  const n = (v: number, broken = false) => <b className={`tabular ${broken ? "rounded bg-ink px-1 text-paper" : ""}`}>{v}</b>;
  return (
    <dl className="mt-3 space-y-1 text-sm">
      <div><dt className="inline text-ink-3">Never lost · </dt><dd className="inline">{n(p.lost.reports)} reports = {n(p.lost.cases)} cases + {n(p.lost.merged)} merged + {n(p.lost.to_check)} to check + {n(p.lost.without_home, p.lost.broken)} without a home</dd></div>
      <div><dt className="inline text-ink-3">Never doubled · </dt><dd className="inline">{n(p.doubled.merged)} merged · {n(p.doubled.to_check, p.doubled.broken)} to check · {n(p.doubled.refused)} refused</dd></div>
      <div><dt className="inline text-ink-3">Never stale · </dt><dd className="inline">{n(p.stale.p1_unowned, p.stale.p1_unowned > 0)} P1 without owner &gt; 5 min · {n(p.stale.overdue, p.stale.overdue > 0)} contact overdue</dd></div>
    </dl>
  );
}

export default function Incidents() {
  const [me, setMe] = useState<Me | null>(null);
  const [list, setList] = useState<Incident[] | null>(null);
  const [out, setOut] = useState(false);

  useEffect(() => {
    api<Me>("/v1/me").then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) setOut(true); });
    const load = () => api<Incident[]>("/v1/incidents").then(setList).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  if (out) {
    return (
      <main className="mx-auto max-w-xl p-10">
        <h1 className="text-3xl font-semibold tracking-tight">RakshaSetu</h1>
        <p className="mt-2 text-ink-2">Never lost. Never doubled. Never stale.</p>
        <p className="mt-8"><a className="underline underline-offset-2" href="/login">Sign in</a></p>
      </main>
    );
  }
  const desk = me && ["call_taker", "duty_officer", "incharge", "admin"].includes(me.user.role);
  const go = (code: string) => { if (desk) location.href = `/desk/${code}`; };
  return (
    <main className="flex min-h-screen flex-col">
      <header className="flex h-12 items-center justify-between border-b border-line px-4">
        <span className="flex items-baseline gap-3"><span className="font-semibold tracking-tight">RakshaSetu</span><span className="text-sm text-ink-2">Incidents</span></span>
        <span className="text-sm text-ink-2">{me?.user.name} <span className="text-ink-3">· {me?.user.role_label}</span>
          {me?.permissions.includes("audit.read") && <a href="/audit" className="ml-4 underline underline-offset-2">Audit</a>}
          {me?.permissions.includes("totals.view") && <a href="/surge" className="ml-4 underline underline-offset-2">Surge</a>}
          {me?.demo_mode && me?.permissions.includes("incident.admin") && <a href="/demo" className="ml-4 underline underline-offset-2">Demo controls</a>}
          <a href="/login" onClick={() => fetch("/v1/auth/logout", { method: "POST" })} className="ml-4 text-ink-3">Sign out</a></span>
      </header>
      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <section className="space-y-3 p-4" aria-label="Incidents">
          {(list ?? []).map((i) => (
            <article key={i.id} className="rounded-xl border border-line p-4">
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="text-lg font-semibold tracking-tight">{i.name} <span className="tabular text-ink-3">{i.code}</span></h2>
                <span className="text-xs text-ink-2">{STATUS[i.status] ?? i.status}</span>
              </div>
              <p className="text-sm text-ink-2">{i.states.join(", ")} · {i.districts.join(" · ")}</p>
              {i.promises && <Bar p={i.promises} />}
              {desk && <a href={`/desk/${i.code}`} className="mt-3 inline-block text-sm font-medium underline underline-offset-2">Open the desk</a>}
            </article>
          ))}
          {me?.user.role === "seoc_viewer" && <p className="text-xs text-ink-3">The SEOC sees totals and capacity requests; the district desks act.</p>}
        </section>
        <div className="min-h-80 border-line lg:border-l">
          {list && <IncidentsMap pins={list.filter((i) => i.lat != null).map((i) => ({ code: i.code, name: i.name, lat: i.lat, lng: i.lng,
                                                                                         broken: !!i.promises && (i.promises.stale.broken || i.promises.lost.broken || i.promises.doubled.broken) }))}
                                 onOpen={go} />}
        </div>
      </div>
    </main>
  );
}

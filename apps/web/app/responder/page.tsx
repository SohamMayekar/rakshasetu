"use client";

// The responder app (PRD F-C7): the team lead logs in as their team. "My cases" with each check-in ring; a NEW
// assignment takes the whole screen with Acknowledge + ETA chips (one tap). New assignments arrive over the
// WebSocket with a vibration and a sound. While the app is open it says "last seen" every 10 s — display only.

import { LifeBuoy } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { useWakeLock } from "@/lib/wakelock";
import { Mark } from "@/components/shell/Sidebar";

import { BigButton, TapStatus } from "@/components/responder/Field";
import { Clock, Priority, Ring } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useLive } from "@/lib/live";
import { tap } from "@/lib/outbox";
import type { MyCase, MyTeam } from "@/lib/responder";

function Login({ onIn }: { onIn: () => void }) {
  const [error, setError] = useState<string | null>(null);
  return (
    <main className="mx-auto min-h-dvh max-w-md bg-canvas px-5 py-8">
      <p className="flex items-center gap-2 text-sm font-semibold"><Mark className="size-6" />RakshaSetu · Team</p>
      <h1 className="mt-6 text-3xl font-semibold tracking-tight">Sign in as your team</h1>
      <form className="mt-6 space-y-3 rounded-[28px] bg-paper p-5 shadow-[var(--shadow-card)]" onSubmit={async (e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        try { await api("/v1/auth/login", { method: "POST", json: { username: f.get("u"), password: f.get("p") } }); onIn(); }
        catch (x) { setError(x instanceof Error ? x.message : String(x)); }
      }}>
        <input name="u" placeholder="Username" autoComplete="username" className="h-14 w-full rounded-xl border border-line px-4 text-lg" />
        <input name="p" type="password" placeholder="Password" autoComplete="current-password" className="h-14 w-full rounded-xl border border-line px-4 text-lg" />
        <BigButton>Sign in</BigButton>
        {error && <p className="text-sm">{error}</p>}
      </form>
    </main>
  );
}

function beep() {
  try {
    const ctx = new AudioContext();
    const o = ctx.createOscillator();
    o.frequency.value = 880; o.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.25);
  } catch { /* no audio: the vibration and the screen still say it */ }
}

const where = (c: MyCase) => `${c.location_text ?? "place not known"}${c.distance_km != null ? ` · ${c.distance_km} km` : ""}`;

function NewCase({ c }: { c: MyCase }) {
  return (
    <main className="fixed inset-0 z-50 flex flex-col bg-paper px-5 pb-6 pt-8">
      <p className="text-sm font-semibold uppercase tracking-widest text-ink-3">New case</p>
      <p className="mt-2 flex items-baseline gap-3 text-4xl font-semibold tracking-tight"><Priority level={c.priority} /><span className="tabular">{c.public_id}</span></p>
      <p className="mt-4 text-2xl leading-snug">{c.summary}</p>
      <p className="mt-2 text-lg text-ink-2">{where(c)}</p>
      {c.priority_reasons.length > 0 && <p className="mt-1 text-sm text-ink-3">{c.priority} because {c.priority_reasons.join(" · ")}</p>}
      <div className="mt-auto space-y-3">
        <p className="text-center text-sm text-ink-2">Acknowledge with your ETA</p>
        <div className="grid grid-cols-3 gap-3">
          {[15, 30, 60].map((m) => (
            <BigButton key={m} variant={m === 30 ? "primary" : "secondary"}
                       onClick={() => tap({ url: `/v1/assignments/${c.assignment_id}/acknowledge`, body: { eta_minutes: m },
                                            label: `Acknowledged · ETA ${m}`, caseId: c.id })}>{m} min</BigButton>
          ))}
        </div>
        <TapStatus caseId={c.id} />
        <a href={`/responder/case/${c.id}`} className="block py-2 text-center text-base underline underline-offset-4">Open the case first</a>
      </div>
    </main>
  );
}

const CACHE = "rs-my-cases";   // the last list this phone had, for when the network is gone

export default function Responder() {
  const [state, setState] = useState<"loading" | "out" | "in">("loading");
  const [team, setTeam] = useState<MyTeam | null>(null);
  const [cases, setCases] = useState<MyCase[]>([]);
  const [since, setSince] = useState<number | null>(null);
  const known = useRef<Set<number>>(new Set());

  const [offlineSince, setOfflineSince] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const r = await api<{ team: MyTeam; cases: MyCase[] }>("/v1/teams/me/cases");
      const fresh = r.cases.filter((c) => !known.current.has(c.assignment_id));
      if (known.current.size && fresh.length) { navigator.vibrate?.([200, 100, 200]); beep(); }
      r.cases.forEach((c) => known.current.add(c.assignment_id));
      setTeam(r.team); setCases(r.cases); setState("in"); setOfflineSince(null);
      try { localStorage.setItem(CACHE, JSON.stringify({ ...r, at: new Date().toISOString() })); } catch { /* storage full */ }
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) { setState("out"); return; }
      // No network: show the last list this phone had, saying how old it is (P1 #7). Taps still save on the phone.
      try {
        const c = JSON.parse(localStorage.getItem(CACHE) ?? "null") as { team: MyTeam; cases: MyCase[]; at: string } | null;
        if (c) { setTeam(c.team); setCases(c.cases); setState("in"); setOfflineSince(c.at); }
      } catch { /* nothing cached */ }
    }
  }, []);
  useWakeLock(cases.some((c) => c.phase === "acknowledged" || c.phase === "reached"));
  useEffect(() => {   // the offline shell (network first) and a re-read whenever the network comes back
    navigator.serviceWorker?.register("/responder-sw.js", { scope: "/responder" }).catch(() => {});
    const back = () => load();
    window.addEventListener("online", back);
    const t = setInterval(load, 30_000);   // a fallback beside the live socket; also how "No network" is noticed
    return () => { window.removeEventListener("online", back); clearInterval(t); };
  }, [load]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {   // the WebSocket cursor: start from "now"
    // (its own list: the only one routed on the public address; the header is read before the list, so nothing is missed)
    if (state === "in" && since == null) fetch("/v1/teams/me/cases").then((r) => setSince(Number(r.headers.get("X-Event-Seq") ?? 0))).catch(() => setSince(0));
  }, [state, since]);
  useLive(team?.incident ?? "BR", state === "in" ? since : null, () => { load(); });
  useEffect(() => {   // "last seen" while open: display only, never extends a check-in
    if (state !== "in") return;
    const beat = () => fetch("/v1/teams/me/heartbeat", { method: "POST" }).catch(() => {});
    beat();
    const t = setInterval(beat, 10_000);
    return () => clearInterval(t);
  }, [state]);

  if (state === "loading") return <main className="p-6 text-ink-3">…</main>;
  if (state === "out") return <Login onIn={load} />;
  const offered = cases.find((c) => c.phase === "offered");
  return (
    <main className="mx-auto min-h-dvh max-w-md bg-canvas px-5 pb-10 pt-6">
      {offered && <NewCase c={offered} />}
      <p className="flex items-center gap-2 text-sm font-semibold"><Mark className="size-6" />RakshaSetu · {team?.name}</p>
      <h1 className="mt-5 text-3xl font-semibold tracking-tight">My cases</h1>
      {offlineSince && (
        <p className="mt-3 rounded-xl bg-ink px-4 py-2 text-base text-paper">
          No network · showing My cases as of <Clock iso={offlineSince} />. Taps are saved on the phone and sent when it&apos;s back.
        </p>
      )}
      {cases.length === 0 && (
        <p className="mt-6 flex items-center gap-3 rounded-[24px] bg-paper px-5 py-6 text-lg text-ink-2 shadow-[var(--shadow-card)]">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-wash text-ink"><LifeBuoy className="size-5" strokeWidth={1.8} aria-hidden /></span>
          No cases assigned to your team right now.
        </p>
      )}
      <ul className="mt-6 space-y-3">
        {cases.map((c) => (
          <li key={c.id}>
            <a href={`/responder/case/${c.id}`} className="block rounded-[24px] bg-paper p-4 shadow-[var(--shadow-card)] active:bg-wash">
              <p className="flex items-baseline justify-between gap-2">
                <span className="flex items-baseline gap-2 text-xl font-semibold"><Priority level={c.priority} /><span className="tabular">{c.public_id}</span></span>
                <span className="text-sm text-ink-2">{{ offered: "new", acknowledged: "on the way", reached: "on scene" }[c.phase]}</span>
              </p>
              <p className="mt-1 text-lg leading-snug">{c.summary}</p>
              <p className="text-ink-2">{where(c)}</p>
              <div className="mt-2"><Ring due={c.next_contact_due} windowMs={Math.max(new Date(c.next_contact_due).getTime() - new Date(c.created_at).getTime(), 60_000)}
                                         overdue={c.state === "overdue"} demo={c.demo_clock} /></div>
            </a>
            {/* the last taps stay visible here: the full-screen New case closes as soon as the server has the tap */}
            <div className="mt-1.5"><TapStatus caseId={c.id} /></div>
          </li>
        ))}
      </ul>
      <p className="mt-8 text-xs text-ink-3">While this screen is open your team shows as &ldquo;last seen&rdquo;. That never counts as a check-in: tap an action or radio the control room.</p>
    </main>
  );
}

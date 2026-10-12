"use client";

// The public status page (PRD F-L3). Polls every 3 s (no WebSocket through the tunnel). Shows the step and
// when it last changed, nothing else: no names, numbers, location, priority or ETA. "Help assigned", never
// "help on the way": we don't know the boat is moving. When a team goes quiet, only "last update" ages.

import { use, useEffect, useState } from "react";

type Status = { public_id: string; tracked_as: string | null; other_reports: number | null; step: string; steps: string[]; last_update_at: string };

const LABEL: Record<string, { hi: string; en: string }> = {
  registered: { hi: "दर्ज", en: "Registered" },
  help_assigned: { hi: "मदद तय", en: "Help assigned" },
  team_reached: { hi: "टीम पहुँची", en: "Team reached" },
  rescued: { hi: "बचा लिया गया", en: "Rescued" },
  closed: { hi: "बंद", en: "Closed" },
};

function ago(iso: string, now: number) {
  const min = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  return `${h} h ${min % 60} min ago`;
}

export default function StatusPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [st, setSt] = useState<Status | null>(null);
  const [missing, setMissing] = useState(false);
  const [offline, setOffline] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const r = await fetch(`/v1/public/cases/${encodeURIComponent(id)}/status`, { cache: "no-store" });
        if (!alive) return;
        if (r.status === 404) return setMissing(true);
        if (r.ok) { setSt(await r.json()); setOffline(false); }
      } catch { if (alive) setOffline(true); }
      if (alive) setNow(Date.now());
    };
    load();
    const t = setInterval(load, 3000);
    return () => { alive = false; clearInterval(t); };
  }, [id]);

  if (missing) {
    return <Shell><p className="text-xl">No case with the number <b className="tabular">{id}</b>.</p></Shell>;
  }
  if (!st) return <Shell><p className="text-neutral-500">…</p></Shell>;

  const current = st.step === "closed" ? -1 : st.steps.indexOf(st.step);
  return (
    <Shell>
      <p className="text-sm font-medium uppercase tracking-wider text-neutral-500">Case</p>
      <p className="tabular text-5xl font-semibold tracking-tight">{st.tracked_as ?? st.public_id}</p>
      {st.tracked_as && (
        <p className="mt-3 rounded-xl bg-neutral-100 px-4 py-3 text-neutral-800">
          Your report {st.public_id} is now tracked as <b className="tabular">{st.tracked_as}</b>, together with{" "}
          {st.other_reports} other report{st.other_reports === 1 ? "" : "s"} about the same family.
        </p>
      )}

      {st.step === "closed" ? (
        <p className="mt-8 text-2xl font-medium">{LABEL.closed.hi} · {LABEL.closed.en}</p>
      ) : (
        <ol className="mt-8 space-y-0" aria-label="Progress">
          {st.steps.map((s, i) => {
            const done = i <= current;
            const now_ = i === current;
            return (
              <li key={s} className="relative flex gap-4 pb-7 last:pb-0">
                {i < st.steps.length - 1 && (
                  <span aria-hidden className={`absolute left-[11px] top-7 h-[calc(100%-20px)] w-0.5 ${i < current ? "bg-neutral-950" : "bg-neutral-200"}`} />
                )}
                <span aria-hidden className={`mt-1 grid size-6 shrink-0 place-items-center rounded-full border-2 ${done ? "border-neutral-950 bg-neutral-950 text-white" : "border-neutral-300 bg-white"}`}>
                  {done && <svg viewBox="0 0 16 16" className="size-3.5" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3.5 8.5l3 3 6-7" /></svg>}
                </span>
                <span className={done ? "text-neutral-950" : "text-neutral-400"}>
                  <span className={`block text-xl ${now_ ? "font-semibold" : ""}`}>{LABEL[s].hi}</span>
                  <span className="block" lang="en">{LABEL[s].en}{now_ ? " · now" : ""}</span>
                </span>
              </li>
            );
          })}
        </ol>
      )}

      <p className="tabular mt-10 text-neutral-600" lang="en">
        Last update {new Date(st.last_update_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} · {ago(st.last_update_at, now)}
        {offline && <span className="block text-amber-700">Can't reach the server right now; showing the last known step.</span>}
      </p>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto min-h-dvh max-w-md px-6 pb-10 pt-8" lang="hi">
      <p className="mb-8 text-sm font-medium tracking-wide text-neutral-500">RakshaSetu</p>
      {children}
      <p className="mt-12 border-t border-neutral-200 pt-6 text-sm text-neutral-600" lang="en">
        You don't need to do anything here. If someone is in danger right now, call <b>112</b> or <b>1077</b>.
      </p>
    </main>
  );
}

"use client";

// The public status page (PRD F-L3). Polls every 3 s (no WebSocket through the tunnel). Shows the step and
// when it last changed, nothing else: no names, numbers, location, priority or ETA. "Help assigned", never
// "help on the way": we don't know the boat is moving. When a team goes quiet, only "last update" ages.

import { use, useEffect, useState } from "react";

import { adoptDevice, deviceId } from "@/lib/device";

type Status = { public_id: string; tracked_as: string | null; other_reports: number | null; step: string; steps: string[]; last_update_at: string;
                check?: { people_taken: number | null; answered: string | null } | null };

const LABEL: Record<string, string> = {
  registered: "Registered",
  help_assigned: "Help assigned",
  team_reached: "Team reached",
  rescued: "Rescued",
  closed: "Closed",
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
    let handed = new URLSearchParams(location.hash.slice(1)).get("device");   // the demo page's QR only
    const load = async (): Promise<void> => {
      try {
        const r = await fetch(`/v1/public/cases/${encodeURIComponent(id)}/status?device=${encodeURIComponent(deviceId())}`, { cache: "no-store" });
        if (!alive) return;
        if (r.status === 404) return setMissing(true);
        if (r.ok) {
          const body = await r.json();
          if (handed && body.demo) {   // never outside DEMO_MODE: the server must say so before the id is taken
            adoptDevice(handed);
            handed = null;
            history.replaceState(null, "", location.pathname);
            return load();
          }
          setSt(body); setOffline(false);
        }
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
        <p className="mt-8 text-2xl font-medium">{LABEL.closed}</p>
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
                  <span className={`block text-xl ${now_ ? "font-semibold" : ""}`}>{LABEL[s]}</span>
                  {now_ && <span className="block text-neutral-600">current step</span>}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      {st.check && <FamilyCheck id={st.tracked_as ?? st.public_id} check={st.check} />}

      <p className="tabular mt-10 text-neutral-600">
        Last update {new Date(st.last_update_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })} · {ago(st.last_update_at, now)}
        {offline && <span className="block text-neutral-950">Can't reach the server right now; showing the last known step.</span>}
      </p>
    </Shell>
  );
}

// The family's optional check (PRD F-S3): shown only to the device that reported this case, after "rescued".
// One question, two answers, and it says plainly that nobody has to answer.
function FamilyCheck({ id, check }: { id: string; check: { people_taken: number | null; answered: string | null } }) {
  const [answer, setAnswer] = useState<string | null>(check.answered);
  const [busy, setBusy] = useState(false);
  const send = async (a: "yes" | "no") => {
    setBusy(true);
    const r = await fetch(`/v1/public/cases/${encodeURIComponent(id)}/confirm`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ device_id: deviceId(), answer: a }) });
    if (r.ok || r.status === 409) setAnswer(a);
    setBusy(false);
  };
  if (answer) {
    return (
      <p className="mt-8 rounded-xl bg-neutral-100 px-4 py-3 text-lg">
        Thank you.{answer === "no" && <span className="block text-base text-neutral-700">An officer will check with the team.</span>}
      </p>
    );
  }
  return (
    <section className="mt-8 rounded-2xl border border-neutral-300 p-5">
      <p className="text-xl leading-snug">The team says {check.people_taken ?? ""} people were rescued. Is that right?</p>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <button disabled={busy} onClick={() => send("yes")} className="min-h-16 rounded-2xl bg-neutral-950 text-lg font-semibold text-white">Yes</button>
        <button disabled={busy} onClick={() => send("no")} className="min-h-16 rounded-2xl border-2 border-neutral-950 text-lg font-semibold">No</button>
      </div>
      <p className="mt-3 text-sm text-neutral-600">You don&rsquo;t have to answer.</p>
    </section>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto min-h-dvh max-w-md px-6 pb-10 pt-8">
      <p className="mb-8 text-sm font-medium tracking-wide text-neutral-500">RakshaSetu</p>
      {children}
      <p className="mt-12 border-t border-neutral-200 pt-6 text-sm text-neutral-600">
        You don't need to do anything here. If someone is in danger right now, call <b>112</b> or <b>1077</b>.
      </p>
    </main>
  );
}

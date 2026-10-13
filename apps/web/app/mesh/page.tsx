"use client";

// "What if there is no signal?" A public explainer with a small animated scene. The relay between phones is a
// SIMULATION and the page says so. What is built today (saved on the phone and sent by itself, handing a message
// to someone nearby, late or repeated reports counted once) is kept apart, in plain words, from what is planned
// (a Bluetooth relay in a native app, which a web page cannot do). Nothing here talks to the server.

import { ArrowLeft, ArrowRight, Check, ChevronDown, Pause, Play, RotateCcw, Smartphone, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Mark } from "@/components/shell/Sidebar";

type Pt = [number, number];
type Who = "A" | "B" | "C" | "E";

const TOWER: Pt = [790, 96];
const DESK: Pt = [800, 330];
const EDGE = 575;   // where the dead zone ends

// Where each phone is at each step (they walk), who holds a copy, and what happens.
const STEPS: {
  at: Record<Who, Pt>; holds: Who[]; link?: [Who, Who]; upload?: Who[]; desk?: boolean; time: string; title: string; body: string;
}[] = [
  { at: { A: [95, 300], B: [250, 150], C: [470, 340], E: [215, 385] }, holds: ["A"], time: "+0 min", title: "A family asks for help, with no signal",
    body: "The request is written on their phone first. Nothing waits for a network to be saved." },
  { at: { A: [95, 300], B: [175, 255], C: [470, 340], E: [150, 345] }, holds: ["A", "B"], link: ["A", "B"], time: "+4 min", title: "A neighbour passes and takes a copy",
    body: "Phones that pass each other hand the request on, locked so the carrier cannot read it. Each keeps it until it can hand it on." },
  { at: { A: [95, 300], B: [345, 215], C: [385, 290], E: [300, 385] }, holds: ["A", "B", "C"], link: ["B", "C"], time: "+11 min", title: "It hops toward the edge of the dead zone",
    body: "Each hop only needs a few metres of range. The request moves as people move." },
  { at: { A: [95, 300], B: [380, 230], C: [630, 235], E: [500, 375] }, holds: ["A", "B", "C"], time: "+19 min", title: "One phone reaches signal",
    body: "The first phone to get a bar of signal becomes the way out for everyone behind it." },
  { at: { A: [95, 300], B: [380, 230], C: [630, 235], E: [620, 340] }, holds: ["A", "B", "C"], upload: ["C"], time: "+19 min", title: "It goes up the tower",
    body: "The phone uploads every request it is carrying, in one go, to the district desk." },
  { at: { A: [95, 300], B: [380, 230], C: [630, 235], E: [620, 340] }, holds: ["A", "B", "C"], desk: true, time: "+20 min", title: "The desk has it, once",
    body: "It lands as one case, marked with when it was really written. If two phones delivered it, the desk keeps one." },
];
const STEP_MS = 3400;

function Phone({ at, label, holds, signal, move, key2 }: { at: Pt; label: string; holds: boolean; signal: boolean; move: boolean; key2: string }) {
  return (
    <g style={{ transform: `translate(${at[0]}px, ${at[1]}px)`, transition: move ? "transform 1.5s cubic-bezier(.22,1,.36,1)" : "none" }}>
      <ellipse cx="0" cy="34" rx="20" ry="5" fill="#151515" opacity=".08" />
      <rect x="-15" y="-27" width="30" height="54" rx="8" fill="#fff" stroke={holds ? "#151515" : "#c9c7c1"} strokeWidth={holds ? 2.4 : 1.6} />
      <rect x="-10" y="-20" width="20" height="36" rx="3.5" fill={holds ? "#151515" : "#efeeea"} />
      {holds && (
        <g key={key2} className="lp-badge">
          <rect x="-8" y="-6" width="16" height="12" rx="2.5" fill="#fff" />
          <path d="M-8 -5l8 6 8-6" fill="none" stroke="#151515" strokeWidth="1.6" strokeLinejoin="round" />
        </g>
      )}
      <text y="46" textAnchor="middle" fontSize="12" fontWeight="600" fill="#55534e">{label}</text>
      {/* signal bars above the phone, only where there is signal */}
      <g transform="translate(-9 -44)" opacity={signal ? 1 : 0} style={{ transition: "opacity .4s" }}>
        <rect x="0" y="8" width="4" height="5" rx="1" fill="#151515" /><rect x="7" y="4" width="4" height="9" rx="1" fill="#151515" /><rect x="14" y="0" width="4" height="13" rx="1" fill="#151515" />
      </g>
    </g>
  );
}

export default function MeshPage() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [dup, setDup] = useState(false);
  const [calm, setCalm] = useState(false);
  const [open, setOpen] = useState<number | null>(0);
  const seen = useRef(false);

  useEffect(() => {
    const reduced = document.documentElement.dataset.motion === "reduced";
    setCalm(reduced);
    if (reduced) setPlaying(false);
    seen.current = true;
  }, []);

  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setStep((s) => (s + 1) % STEPS.length), step === STEPS.length - 1 ? STEP_MS + 1400 : STEP_MS);
    return () => clearTimeout(t);
  }, [playing, step]);

  const cur = STEPS[step];
  const holds = useMemo(() => new Set<Who>([...cur.holds, ...(dup && step >= 1 ? (["E"] as Who[]) : [])]), [cur, dup, step]);
  const uploads = useMemo<Who[]>(() => [...(cur.upload ?? []), ...(dup && step >= 4 ? (["E"] as Who[]) : [])], [cur, dup, step]);
  const inSignal = (w: Who) => cur.at[w][0] > EDGE;
  const phones: [Who, string][] = [["A", "Family"], ["B", "Neighbour"], ["C", "Passer-by"], ...(dup ? ([["E", "Another"]] as [Who, string][]) : [])];
  const log = STEPS.slice(0, step + 1);
  const link = cur.link ? [cur.at[cur.link[0]], cur.at[cur.link[1]]] : null;
  const linkLen = link ? Math.ceil(Math.hypot(link[0][0] - link[1][0], link[0][1] - link[1][1])) : 0;

  return (
    <div className="lp min-h-dvh">
      <div className="lp-hero-bg">
        <div className="mx-auto max-w-5xl px-4 pb-10 pt-6 sm:px-6">
          <header className="flex items-center justify-between">
            <a href="/" className="flex items-center gap-2 text-body font-semibold"><Mark className="size-6" />RakshaSetu</a>
            <a href="/r" className="inline-flex h-10 items-center gap-1.5 rounded-full bg-ink px-4 text-body font-semibold text-paper">I need help<ArrowRight className="size-4" aria-hidden /></a>
          </header>
          <div className="mx-auto mt-12 max-w-3xl text-center">
            <h1 className="text-[2.2rem] font-semibold leading-[1.06] tracking-[-0.035em] sm:text-5xl">
              A request for help should not need <em className="lp-em">a network</em> to be saved.
            </h1>
            <p className="mx-auto mt-4 max-w-2xl text-[1.0625rem] leading-relaxed text-ink-2">
              In a disaster, towers and power go down first. RakshaSetu keeps a request on the phone that made it, and is built so it can travel from phone to phone until one of them reaches signal.
            </p>
            <p className="mt-5 inline-flex items-center gap-2 rounded-full border border-line bg-paper/85 px-3.5 py-1.5 text-small font-medium text-ink-2 backdrop-blur">
              <span className="size-2 rounded-full bg-[var(--lp-accent)]" aria-hidden />Simulation. The phone-to-phone relay is a design we show, not a feature switched on today.
            </p>
          </div>
        </div>
      </div>

      <main className="mx-auto -mt-2 max-w-5xl px-4 pb-20 sm:px-6">
        <section aria-label="Animation: a request travelling through phones" className="overflow-hidden rounded-[28px] border border-line/80 bg-paper shadow-[var(--shadow-lift)]">
          <div className="relative">
            {/* story-style progress, clickable */}
            <div className="absolute inset-x-4 top-3 z-10 flex gap-1.5" role="group" aria-label="Steps">
              {STEPS.map((s, i) => (
                <button key={s.title} type="button" onClick={() => setStep(i)} aria-label={`Step ${i + 1}: ${s.title}`} className="group h-5 flex-1">
                  <span className="mt-2 block h-1 overflow-hidden rounded-full bg-ink/10 transition-[height] group-hover:h-1.5">
                    <span className={`block h-full rounded-full bg-ink ${i < step ? "w-full" : i === step ? (calm ? "w-full" : "lp-fill w-full") : "w-0"}`}
                          style={i === step && !calm ? { animationDuration: `${STEP_MS}ms`, animationPlayState: playing ? "running" : "paused" } : undefined}
                          key={i === step ? `${step}-${playing}` : i} />
                  </span>
                </button>
              ))}
            </div>

            <svg viewBox="0 0 900 440" className="block w-full" role="img" aria-label={`${cur.title}. ${cur.body}`}>
              <defs>
                <linearGradient id="mz-dead" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stopColor="#ecebe7" /><stop offset="1" stopColor="#f4f3f0" /></linearGradient>
                <linearGradient id="mz-live" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stopColor="#e6eff7" /><stop offset="1" stopColor="#f8ecda" /></linearGradient>
                <pattern id="mz-hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line x1="0" y1="0" x2="0" y2="14" stroke="#151515" strokeOpacity=".05" strokeWidth="2" /></pattern>
              </defs>
              <rect width="900" height="440" fill="url(#mz-live)" />
              <path d={`M0 0 H${EDGE} q-26 110 0 220 q26 110 0 220 H0 Z`} fill="url(#mz-dead)" />
              <path d={`M0 0 H${EDGE} q-26 110 0 220 q26 110 0 220 H0 Z`} fill="url(#mz-hatch)" />
              <path d={`M${EDGE} 0 q-26 110 0 220 q26 110 0 220`} fill="none" stroke="#bdbab2" strokeWidth="2" strokeDasharray="7 8" />
              <text x="26" y="62" fontSize="13" fontWeight="700" letterSpacing="1.4" fill="#8c8a85">NO SIGNAL</text>
              <text x="640" y="62" fontSize="13" fontWeight="700" letterSpacing="1.4" fill="#1f4e79">SIGNAL</text>

              {/* a few buildings in the dead zone */}
              <g fill="#d7d5cf">
                <rect x="40" y="318" width="110" height="64" rx="6" /><rect x="170" y="338" width="70" height="44" rx="6" /><rect x="410" y="100" width="90" height="58" rx="6" /><rect x="300" y="96" width="60" height="40" rx="6" />
              </g>
              <path d="M0 410 H560" stroke="#cfcdc7" strokeWidth="14" strokeLinecap="round" opacity=".7" />

              {/* the tower and the desk */}
              <g transform={`translate(${TOWER[0]} ${TOWER[1]})`}>
                {[0, 1, 2].map((i) => <circle key={i} className="lp-ring-out lp-svg-origin" r="26" fill="none" stroke="#1f4e79" strokeWidth="2" style={{ animationDelay: `${i * 800}ms` }} />)}
                <path d="M0 -30 L-14 40 M0 -30 L14 40 M-8 6h16 M-11 22h22" stroke="#151515" strokeWidth="3.2" fill="none" strokeLinecap="round" />
                <circle cy="-32" r="6" fill="#151515" />
                <text y="62" textAnchor="middle" fontSize="12" fontWeight="600" fill="#55534e">Tower</text>
              </g>
              <g transform={`translate(${DESK[0] - 74} ${DESK[1] - 32})`}>
                <rect width="148" height="68" rx="16" fill={cur.desk ? "#151515" : "#fff"} stroke="#151515" strokeWidth="1.6" style={{ transition: "fill .5s" }} />
                <text x="74" y="28" textAnchor="middle" fontSize="13" fontWeight="700" fill={cur.desk ? "#fff" : "#151515"}>District desk</text>
                <text x="74" y="49" textAnchor="middle" fontSize="12" fill={cur.desk ? "#ffffffcc" : "#55534e"}>
                  {cur.desk ? (dup ? "2 copies, 1 case" : "1 new case") : "waiting"}
                </text>
              </g>

              {/* a hand-off between two phones */}
              {link && (
                <g key={`link-${step}`}>
                  <line x1={link[0][0]} y1={link[0][1]} x2={link[1][0]} y2={link[1][1]} stroke="#1f4e79" strokeWidth="3" strokeLinecap="round" className="lp-draw" style={{ ["--len" as string]: linkLen }} />
                  <circle cx={link[1][0]} cy={link[1][1]} r="30" fill="none" stroke="#1f4e79" strokeWidth="2" className="lp-ring-out lp-svg-origin" />
                </g>
              )}
              {dup && step === 1 && (
                <line key="dup-link" x1={cur.at.A[0]} y1={cur.at.A[1]} x2={cur.at.E[0]} y2={cur.at.E[1]} stroke="#1f4e79" strokeWidth="3" strokeLinecap="round" className="lp-draw" style={{ ["--len" as string]: 90 }} />
              )}

              {/* the way out: phone → tower → desk */}
              {uploads.map((w) => (
                <g key={`up-${w}-${step}`}>
                  <path d={`M${cur.at[w][0]} ${cur.at[w][1] - 30} L${TOWER[0]} ${TOWER[1] + 40}`} stroke="#1f4e79" strokeWidth="3" fill="none" strokeLinecap="round" className="lp-dash" />
                </g>
              ))}
              {(cur.desk || uploads.length > 0) && (
                <path d={`M${TOWER[0]} ${TOWER[1] + 66} L${DESK[0]} ${DESK[1] - 34}`} stroke="#1f4e79" strokeWidth="3" fill="none" strokeLinecap="round" className="lp-dash" />
              )}

              {phones.map(([w, label]) => (
                <Phone key={w} at={cur.at[w]} label={label} holds={holds.has(w)} signal={inSignal(w)} move={!calm} key2={`${w}-${step}-${holds.has(w)}`} />
              ))}
            </svg>
          </div>

          <div className="grid gap-5 border-t border-line p-5 sm:p-6 lg:grid-cols-[1fr_auto]">
            <div aria-live="polite" className="min-w-0">
              <p className="flex items-center gap-2 text-small font-semibold text-ink-3">
                <span className="tabular rounded-full bg-[var(--lp-wash)] px-2 py-0.5 text-[var(--lp-accent-ink)]">{cur.time}</span>
                Step {step + 1} of {STEPS.length}
              </p>
              <p className="mt-2 text-xl font-semibold tracking-[-0.02em]">{cur.title}</p>
              <p className="mt-1 max-w-2xl text-[0.9375rem] leading-relaxed text-ink-2">{cur.body}</p>
              {dup && step === 5 && <p className="mt-2 text-[0.9375rem] font-semibold">It arrived twice, by two routes. Counted once, because both copies carry the same request id.</p>}
            </div>
            <div className="flex flex-wrap items-start gap-2 lg:justify-end">
              <button onClick={() => setStep((s) => (s + STEPS.length - 1) % STEPS.length)} aria-label="Previous step" className="grid size-11 place-items-center rounded-full border border-line hover:bg-wash"><ArrowLeft className="size-4" aria-hidden /></button>
              <button onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause" : "Play"} className="grid size-11 place-items-center rounded-full bg-ink text-paper hover:bg-[#2b2b2b]">{playing ? <Pause className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}</button>
              <button onClick={() => setStep((s) => (s + 1) % STEPS.length)} aria-label="Next step" className="grid size-11 place-items-center rounded-full border border-line hover:bg-wash"><ArrowRight className="size-4" aria-hidden /></button>
              <button onClick={() => { setStep(0); setPlaying(!calm); }} aria-label="Start again" className="grid size-11 place-items-center rounded-full border border-line hover:bg-wash"><RotateCcw className="size-4" aria-hidden /></button>
            </div>
          </div>

          <div className="grid gap-4 border-t border-line bg-canvas/60 p-5 sm:p-6 md:grid-cols-[1fr_16rem]">
            <ol aria-label="What each phone did" className="space-y-1.5">
              {log.map((s, i) => (
                <li key={s.title} className="lp-log-in flex items-baseline gap-3 text-small">
                  <span className="tabular w-14 shrink-0 font-semibold text-[var(--lp-accent)]">{s.time}</span>
                  <span className={i === step ? "font-semibold text-ink" : "text-ink-2"}>{s.title}</span>
                </li>
              ))}
            </ol>
            <div>
              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-line bg-paper p-3.5 text-small leading-snug">
                <input type="checkbox" checked={dup} onChange={(e) => { setDup(e.target.checked); setStep(0); }} className="mt-0.5 size-4 accent-[#151515]" />
                <span><b className="font-semibold">Two phones carry the same request.</b> It arrives twice and is counted once.</span>
              </label>
              <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
                {[["Copies", String(holds.size)], ["Hops", String(Math.min(step, 2))], ["Delivered", cur.desk ? "1" : "0"]].map(([k, v]) => (
                  <div key={k} className="rounded-2xl bg-paper px-2 py-2.5"><dd className="tabular text-xl font-semibold leading-none">{v}</dd><dt className="mt-1 text-micro text-ink-3">{k}</dt></div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        <section className="mt-10 grid gap-4 lg:grid-cols-2" aria-label="What is real today">
          <div className="rounded-[24px] border border-line/80 bg-paper p-6 shadow-[var(--shadow-card)]">
            <h2 className="flex items-center gap-2.5 text-heading font-semibold"><span className="grid size-9 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><Check className="size-5" aria-hidden /></span>Working today</h2>
            <ul className="mt-4 space-y-3.5 text-body leading-snug text-ink-2">
              <li><b className="text-ink">Saved on the phone, sent by itself.</b> With no signal, a typed or spoken request is kept on the phone and sent the moment there is signal again, with no second tap. Try it: switch on airplane mode on the help page.</li>
              <li><b className="text-ink">Pass it on.</b> The help page can hand the request to someone nearby, who can forward it by WhatsApp or SMS. The desk reads forwarded messages like any other report.</li>
              <li><b className="text-ink">Late is fine, twice is fine.</b> A request carries its own id and the time it was written. If it arrives hours late, or twice, the desk shows the real time and keeps one case.</li>
              <li><b className="text-ink">Team phones too.</b> A responding team’s taps are saved on the phone and sent when signal returns, and a repeated tap never acts twice.</li>
            </ul>
          </div>
          <div className="rounded-[24px] border border-line/80 bg-paper p-6 shadow-[var(--shadow-card)]">
            <h2 className="flex items-center gap-2.5 text-heading font-semibold"><span className="grid size-9 place-items-center rounded-xl bg-amber-100 text-amber-700"><X className="size-5" aria-hidden /></span>Planned, not built yet</h2>
            <ul className="mt-4 space-y-3.5 text-body leading-snug text-ink-2">
              <li><b className="text-ink">Phone-to-phone relay over Bluetooth.</b> The animation above. A web page cannot send or listen for Bluetooth messages in the background, so this needs a small native app on Android. The server side it needs is already there: one id per request, the written-at time, and counting a request once.</li>
              <li><b className="text-ink">Locked for the carrier.</b> Each request would be sealed to the desk’s key, so a phone carrying it cannot read it. The signing keys are not built.</li>
              <li><b className="text-ink">Not a replacement for 112.</b> A relay can be slow, and depends on people moving. The help page always says to call 112 or 1077 when someone is in danger right now.</li>
            </ul>
          </div>
        </section>

        <section className="mt-4 rounded-[24px] border border-line/80 bg-paper p-6 shadow-[var(--shadow-card)]" aria-labelledby="ask-h">
          <h2 id="ask-h" className="flex items-center gap-2.5 text-heading font-semibold"><span className="grid size-9 place-items-center rounded-xl bg-sky-100 text-sky-700"><Smartphone className="size-5" aria-hidden /></span>If you are asked</h2>
          <ul className="mt-3 divide-y divide-ink/10">
            {[
              ["Is the Bluetooth mesh live?", "No, and we say so. What is live is saving on the phone and sending when signal returns. The relay is designed and the server is ready for it, but it needs a native app."],
              ["Why not just use the browser?", "Browsers can’t advertise or scan Bluetooth in the background, and iPhones allow even less. That is a platform rule, not a choice."],
              ["Can a stranger’s phone read a report?", "Not in the design: each request is sealed to the desk. Today nothing is relayed, so nothing is exposed."],
              ["What stops fake or repeated requests?", "Each request has one id, so repeats merge. A person at the desk still checks and decides, as with every report."],
            ].map(([q, a], i) => (
              <li key={q}>
                <button type="button" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i} className="flex w-full items-center justify-between gap-4 py-4 text-left text-[1.0625rem] font-semibold">
                  {q}<ChevronDown className={`size-5 shrink-0 text-ink-3 transition-transform duration-300 ${open === i ? "rotate-180" : ""}`} aria-hidden />
                </button>
                <div className="lp-acc" data-open={open === i}><div><p className="pb-4 pr-8 text-body leading-relaxed text-ink-2">{a}</p></div></div>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}

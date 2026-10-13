"use client";

// "The whole product in 20 seconds": one family's rescue, told in five short scenes on the right device (a phone,
// or the desk), with a story-style progress bar, and a numbered list beside it that you can click through.
// It plays by itself while it is on screen, pauses under the pointer or on request, and never autoplays for
// someone who asked for less motion.

import { Check, CheckCheck, HelpingHand, MapPin, Mic, Pause, PhoneCall, Play, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { delay, Em, H2, IconWell, panel } from "./parts";

type Step = { icon: LucideIcon; who: string; title: string; line: string; device: "phone" | "desk" };

const STEPS: Step[] = [
  { icon: Mic, who: "A daughter, far away", title: "Asks for help", line: "She speaks into any phone. No app, no login, nothing to remember.", device: "phone" },
  { icon: MapPin, who: "The district desk", title: "Joins it into one case", line: "Three reports about one family become one case, with the reasons shown and a person able to undo it.", device: "desk" },
  { icon: HelpingHand, who: "Rescue team 5", title: "One team takes it", line: "One owner and one accepted job. Nobody else is sent by accident.", device: "phone" },
  { icon: Users, who: "Rescue team 5", title: "Counts who came out", line: "“4 taken, someone still there.” The case stays open until the count is whole.", device: "phone" },
  { icon: CheckCheck, who: "The family", title: "Confirms they are safe", line: "Their own phone asks “Is that right?”. Only then is the case closed.", device: "phone" },
];
const STEP_MS = 4800;

/* ---------------------------------------------------------------- device frames */

function PhoneFrame({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="lp-phone mx-auto w-[16.75rem] overflow-hidden bg-canvas sm:w-[17.75rem]">
      <div className="flex items-center justify-between px-5 pb-1 pt-3.5">
        <span className="h-1.5 w-12 rounded-full bg-ink/85" aria-hidden />
        <span className="text-micro font-semibold uppercase tracking-wider text-ink-3">{label}</span>
      </div>
      <div className="min-h-[21.5rem] px-4 pb-5 pt-2">{children}</div>
    </div>
  );
}

function DeskFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[26rem] overflow-hidden rounded-[20px] border border-ink/10 bg-paper shadow-[var(--shadow-lift)]">
      <div className="flex items-center gap-1.5 border-b border-line bg-wash px-3 py-2">
        <i className="size-2 rounded-full bg-ink/20" /><i className="size-2 rounded-full bg-ink/20" /><i className="size-2 rounded-full bg-ink/20" />
        <span className="ml-2 min-w-0 flex-1 truncate rounded-md bg-paper px-2 py-0.5 text-micro text-ink-3">RakshaSetu · National desk</span>
      </div>
      <div className="min-h-[22rem] p-4">{children}</div>
    </div>
  );
}

/* ---------------------------------------------------------------- the five scenes */

function Scene({ step }: { step: number }) {
  if (step === 0) {
    return (
      <PhoneFrame label="Family’s phone">
        <p className="text-small font-semibold text-ink-2">Ask for help</p>
        <div className="relative mx-auto mt-5 grid size-28 place-items-center">
          {[0, 1, 2].map((i) => <span key={i} className="lp-ring-out absolute inset-0 rounded-full border-2 border-[var(--lp-accent)]/45" style={delay(i * 800)} />)}
          <span className="relative grid size-20 place-items-center rounded-full bg-ink text-paper">
            <span className="lp-wave flex h-8 items-center gap-[3px]" aria-hidden>
              {[0, 1, 2, 3, 4, 5, 6].map((i) => <i key={i} style={{ animationDelay: `${i * 90}ms` }} />)}
            </span>
          </span>
        </div>
        <p className="mt-4 text-center text-small text-ink-2">Listening…</p>
        <div className="mt-4 rounded-[20px] bg-paper p-3.5 shadow-[var(--shadow-card)]">
          <p className="lp-type text-[0.9375rem] leading-snug" lang="hi">“छह लोग फँसे हैं, एक बच्चा भी है, जल्दी मदद चाहिए”</p>
          <p className="mt-1.5 text-small text-ink-2">Kept exactly as said, beside every fact.</p>
        </div>
      </PhoneFrame>
    );
  }
  if (step === 1) {
    const src = ["Daughter · voice message, 06:41", "Neighbour · forwarded text, 07:02", "Volunteer sheet · row 118"];
    return (
      <DeskFrame>
        <p className="text-small font-semibold text-ink-2">Three reports, one household</p>
        <ul className="mt-3 space-y-2">
          {src.map((t, i) => (
            <li key={t} className="lp-fly flex items-center gap-2.5 rounded-2xl border border-line bg-paper px-3 py-2.5 text-small"
                style={{ ...delay(i * 160), ["--fx" as string]: "-36px" }}>
              <PhoneCall className="size-4 shrink-0 text-ink-3" aria-hidden />{t}
            </li>
          ))}
        </ul>
        <div className="lp-pop mt-3 rounded-[20px] bg-ink p-4 text-paper" style={delay(900)}>
          <p className="text-micro font-semibold uppercase tracking-wider text-paper/60">One case</p>
          <p className="mt-1 text-[1.0625rem] font-semibold"><span aria-hidden>▲ </span>CASE-214 · 6 people · Urgent</p>
          <p className="mt-0.5 text-small text-paper/70">Same village · same landmarks · circles overlap</p>
        </div>
        <p className="lp-pop mt-3 text-small text-ink-2" style={delay(1300)}>Rajesh ≠ Ramesh: a different family on the same street is never merged.</p>
      </DeskFrame>
    );
  }
  if (step === 2) {
    return (
      <PhoneFrame label="Team 5’s phone">
        <p className="text-small font-semibold text-ink-2">New case</p>
        <div className="mt-3 rounded-[20px] bg-paper p-4 shadow-[var(--shadow-card)]">
          <p className="text-small font-semibold text-p1"><span aria-hidden>▲ </span>Urgent</p>
          <p className="mt-1 text-[1.0625rem] font-semibold leading-snug">6 trapped, one infant</p>
          <p className="mt-0.5 text-small text-ink-2">Station Road · within 150 m of the school</p>
        </div>
        <div className="lp-press mt-4 grid h-16 place-items-center rounded-[20px] bg-ink text-[1.0625rem] font-semibold text-paper">Accept this case</div>
        <p className="lp-pop mt-4 flex items-center gap-2 rounded-2xl bg-[var(--lp-wash)] px-3.5 py-3 text-small font-semibold text-[var(--lp-accent-ink)]" style={delay(1500)}>
          <Check className="size-4 shrink-0" aria-hidden />Accepted. We will be there in 15 minutes.
        </p>
      </PhoneFrame>
    );
  }
  if (step === 3) {
    return (
      <PhoneFrame label="Team 5’s phone">
        <p className="text-small font-semibold text-ink-2">Record the rescue</p>
        <p className="tabular mt-3 text-[2.5rem] font-semibold leading-none tracking-tight">4 <span className="text-xl font-medium text-ink-3">of 6 taken</span></p>
        <ul className="mt-5 grid grid-cols-6 gap-2" aria-label="Six people, four taken to safety">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <li key={i} className={`lp-dot grid aspect-square place-items-center rounded-full ${i < 4 ? "bg-ink text-paper" : "border-2 border-dashed border-ink/35 text-ink-3"}`} style={delay(300 + i * 160)}>
              {i < 4 ? <Check className="size-3.5" aria-hidden /> : <span className="text-micro">?</span>}
            </li>
          ))}
        </ul>
        <p className="lp-pop mt-5 rounded-2xl bg-wash px-3.5 py-3 text-small font-medium" style={delay(1300)}>Someone is still there. The desk keeps the case open and sends the team again.</p>
      </PhoneFrame>
    );
  }
  return (
    <PhoneFrame label="Family’s phone">
      <p className="text-small font-semibold text-ink-2">A message about your family</p>
      <p className="mt-3 text-[1.0625rem] font-semibold leading-snug">The team says 6 people were rescued. Is that right?</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <span className="lp-press grid h-14 place-items-center rounded-[20px] bg-ink text-[1.0625rem] font-semibold text-paper">Yes</span>
        <span className="grid h-14 place-items-center rounded-[20px] border border-line bg-paper font-medium text-ink-2">Not yet</span>
      </div>
      <div className="lp-pop mt-4 flex items-center gap-3 rounded-[20px] bg-ink p-4 text-paper" style={delay(1500)}>
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-paper text-ink"><CheckCheck className="size-5" aria-hidden /></span>
        <p className="text-small leading-snug"><span className="block text-[1.0625rem] font-semibold">Rescued 6 of 6</span>Confirmed by the family</p>
      </div>
    </PhoneFrame>
  );
}

/* ---------------------------------------------------------------- the section */

export function Watch() {
  const [step, setStep] = useState(0);
  const [hover, setHover] = useState(false);
  const [seen, setSeen] = useState(false);
  const [paused, setPaused] = useState(false);
  const [calm, setCalm] = useState(false);
  const box = useRef<HTMLElement>(null);

  useEffect(() => {
    setCalm(document.documentElement.dataset.motion === "reduced");
    const el = box.current;
    if (!el || !("IntersectionObserver" in window)) { setSeen(true); return; }
    const io = new IntersectionObserver(([e]) => setSeen(e.isIntersecting), { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const playing = seen && !hover && !paused && !calm;
  useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => setStep((s) => (s + 1) % STEPS.length), STEP_MS);
    return () => clearTimeout(t);
  }, [playing, step]);

  const cur = STEPS[step];

  return (
    <section id="watch" ref={box} aria-labelledby="watch-h" className="mx-auto max-w-7xl scroll-mt-24 px-4 py-20 sm:px-6 lg:py-28">
      <div className="rv max-w-2xl">
        <H2><span id="watch-h">The whole product in 20 seconds.</span> <Em>One family, start to safe.</Em></H2>
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-[0.82fr_1.18fr] lg:items-start lg:gap-12" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
        {/* the stage: first on a phone, so the picture is the first thing you see */}
        <div className={`rv relative order-1 overflow-hidden lg:order-2 ${panel} bg-gradient-to-b from-[#dbe8f3] via-[#e9eef0] to-[#f2e8d9] p-4 sm:p-6`}>
          <div className="flex items-center gap-1.5" role="group" aria-label="Story progress">
            {STEPS.map((s, i) => (
              <button key={s.title} type="button" onClick={() => setStep(i)} aria-label={`Step ${i + 1}: ${s.title}`}
                      className="group relative h-6 flex-1 outline-offset-2">
                <span className="absolute inset-x-0 top-1/2 block h-1 -translate-y-1/2 overflow-hidden rounded-full bg-ink/12 transition-[height] group-hover:h-1.5">
                  <span className={`absolute inset-0 rounded-full bg-ink ${i < step ? "" : "scale-x-0"}`} />
                  {i === step && !calm && (
                    <span key={`${step}-${playing}`} className="lp-fill absolute inset-0 rounded-full bg-ink"
                          style={{ animationDuration: `${STEP_MS}ms`, animationPlayState: playing ? "running" : "paused" }} />
                  )}
                  {i === step && calm && <span className="absolute inset-0 rounded-full bg-ink" />}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-3 flex items-center justify-between gap-3">
            <p className="text-small font-semibold text-ink-2"><span className="tabular">{step + 1}</span> of {STEPS.length} · {cur.who}</p>
            {!calm && (
              <button type="button" onClick={() => setPaused((p) => !p)} aria-label={paused ? "Play the story" : "Pause the story"}
                      className="grid size-9 place-items-center rounded-full border border-ink/10 bg-paper/80 text-ink-2 hover:text-ink">
                {paused || !seen ? <Play className="size-4" aria-hidden /> : <Pause className="size-4" aria-hidden />}
              </button>
            )}
          </div>

          <div className="mt-4 grid min-h-[27rem] place-items-center py-2" aria-live="polite">
            <div key={step} className="lp-scene w-full"><Scene step={step} /></div>
          </div>
        </div>

        {/* the list: the same five steps, to read or to click */}
        <ol className="order-2 space-y-1.5 lg:order-1" aria-label="The five steps of a rescue">
          {STEPS.map((s, i) => {
            const on = i === step;
            return (
              <li key={s.title}>
                <button type="button" onClick={() => setStep(i)} aria-current={on ? "step" : undefined}
                        className={`flex w-full items-start gap-4 rounded-[24px] border p-4 text-left transition-[background-color,border-color,box-shadow] duration-300 ${on ? "border-line bg-paper shadow-[var(--shadow-card)]" : "border-transparent hover:bg-paper/60"}`}>
                  <span className={`tabular w-7 shrink-0 pt-1 text-2xl font-semibold leading-none tracking-tight transition-colors ${on ? "text-[var(--lp-accent)]" : "text-ink/20"}`}>{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="block text-[1.0625rem] font-semibold leading-snug">{s.title}</span>
                    </span>
                    <span className="block text-small text-ink-3">{s.who}</span>
                    <span className={`grid transition-[grid-template-rows,opacity] duration-300 ${on ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
                      <span className="overflow-hidden"><span className="block pt-2 text-[0.9375rem] leading-snug text-ink-2">{s.line}</span></span>
                    </span>
                  </span>
                  <IconWell icon={s.icon} size="sm" />
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

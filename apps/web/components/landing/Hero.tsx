"use client";

// The first screen, after the reference mood: a soft sky, one line, one sentence, a phone with the product on it and
// a few voices floating around it, over hills and a bridge. A photograph made for the page can replace the drawn
// hills (public/images/hero.webp or .jpg, prompt in docs/HERO_IMAGE.md): it fades in over them if it exists.
// Nothing on this screen is about one kind of disaster or one kind of team.

import { ArrowRight, CheckCheck, HelpingHand, Mic, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { Mark } from "@/components/shell/Sidebar";

import { btnPrimary, btnSecondary, delay, Em, Landscape } from "./parts";

const SOURCES = ["/images/hero.webp", "/images/hero.jpg"];

function Backdrop() {
  const [i, setI] = useState(0);
  const src = SOURCES[i];
  return (
    <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[34rem]">
      <Landscape className="absolute inset-0 size-full" />
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={src} src={src} alt="" className="absolute inset-0 size-full object-cover object-bottom opacity-0 transition-opacity duration-700 [mask-image:linear-gradient(to_top,#000_55%,transparent)]"
             onLoad={(e) => { e.currentTarget.style.opacity = "1"; }} onError={() => setI((n) => n + 1)} />
      )}
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-canvas to-transparent" />
    </div>
  );
}

// The phone, with the product on its screen, and the voices around it.
function PhoneStage() {
  return (
    <div className="relative mx-auto mt-14 w-full max-w-3xl">
      <div className="lp-rise lp-bob absolute -left-1 top-10 z-10 hidden w-64 items-start gap-3 rounded-[20px] border border-line bg-paper p-3.5 shadow-[var(--shadow-lift)] sm:flex lg:-left-12" style={delay(520)}>
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-ink text-paper"><Mic className="size-5" aria-hidden /></span>
        <p className="text-left text-small leading-snug" lang="hi">“छह लोग फँसे हैं, एक बच्चा भी है…”
          <span className="mt-1 block text-micro font-semibold uppercase tracking-wider text-ink-3">Voice message, kept as said</span></p>
      </div>
      <div className="lp-rise lp-bob-slow absolute -right-1 top-24 z-10 hidden w-60 rounded-[20px] border border-line bg-paper p-3.5 text-left shadow-[var(--shadow-lift)] sm:block lg:-right-12" style={delay(680)}>
        <p className="flex items-center gap-1.5 text-small font-semibold"><HelpingHand className="size-4 text-[var(--lp-accent)]" aria-hidden />Team 5 reached them</p>
        <p className="mt-1 text-small text-ink-2">4 taken, someone still there</p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-wash"><div className="h-full w-2/3 rounded-full bg-[var(--lp-accent)]" /></div>
      </div>
      <div className="lp-rise lp-bob absolute -bottom-3 left-4 z-10 hidden items-center gap-2 rounded-full border border-line bg-paper px-4 py-2.5 text-small font-semibold shadow-[var(--shadow-lift)] sm:flex lg:left-14" style={delay(820)}>
        <CheckCheck className="size-4 text-[var(--lp-accent)]" aria-hidden />Family confirmed: 6 of 6 safe
      </div>

      <div className="lp-rise lp-phone mx-auto w-[17rem] overflow-hidden bg-canvas sm:w-[19rem]" style={delay(300)}>
        <div className="space-y-3 px-4 pb-5 pt-9 text-left">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-2 text-body font-semibold"><Mark className="size-6" />RakshaSetu</p>
            <span className="rounded-full bg-wash px-2 py-0.5 text-micro font-semibold uppercase tracking-wider text-ink-2">Demo</span>
          </div>
          <div className="rounded-[20px] bg-ink p-4 text-paper">
            <p className="text-micro font-semibold uppercase tracking-wider text-paper/60">Ask for help</p>
            <p className="mt-1 text-heading font-semibold leading-snug">What is happening, and where?</p>
            <span className="mt-3 inline-flex h-10 items-center gap-2 rounded-full bg-paper px-4 text-small font-semibold text-ink"><Mic className="size-4" aria-hidden />Tap and speak</span>
          </div>
          <div className="relative h-28 overflow-hidden rounded-[20px] bg-[#e7eef3]">
            <div className="lp-grid absolute inset-0 opacity-90" />
            <span className="lp-circle absolute left-1/2 top-1/2 -ml-9 -mt-9 size-[4.5rem] rounded-full border-2 border-dashed border-ink/60 bg-ink/[.07]" />
            <span className="absolute left-1/2 top-1/2 -ml-1 -mt-1 size-2 rounded-full bg-ink" />
            <span className="absolute left-2 top-2 rounded-full bg-paper px-2 py-0.5 text-micro font-semibold shadow-sm">Primary school</span>
          </div>
          <div className="rounded-[20px] bg-paper p-3">
            <div className="flex items-center justify-between"><span className="text-small font-semibold text-p1"><span aria-hidden>▲ </span>Urgent</span><span className="tabular text-small text-ink-3">CASE-214</span></div>
            <p className="mt-0.5 text-small font-medium">6 people · within 150 m of the school</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Hero() {
  return (
    <section id="top" aria-labelledby="hero-title" className="lp-hero-bg relative isolate overflow-hidden">
      <div className="mx-auto max-w-6xl px-4 pt-28 text-center sm:px-6 lg:pt-36">
        <p className="lp-rise mx-auto inline-flex items-center gap-2 rounded-full border border-line bg-paper/80 px-3.5 py-1.5 text-small font-medium text-ink-2 backdrop-blur">
          <ShieldCheck className="size-4" aria-hidden />National incident command, from the first report to the last confirmation
        </p>
        <h1 id="hero-title" className="lp-rise mt-6 text-[2.6rem] font-semibold leading-[1.04] tracking-[-0.035em] sm:text-6xl lg:text-[4.4rem]" style={delay(80)}>
          One command layer for<br /><Em>every emergency.</Em>
        </h1>
        <p className="lp-rise mx-auto mt-6 max-w-2xl text-[1.0625rem] leading-relaxed text-ink-2 sm:text-lg" style={delay(160)}>
          Floods, cyclones, fires, collapses, landslides, accidents. Calls, messages and sheets from anywhere become{" "}
          <strong className="font-semibold text-ink">one case each</strong>, with{" "}
          <strong className="font-semibold text-ink">one accountable team</strong>, followed until the people are confirmed safe.
        </p>
        <div className="lp-rise mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row" style={delay(240)}>
          <a href="/r" className={btnPrimary}>I need help<ArrowRight className="size-4" aria-hidden /></a>
          <a href="#watch" className={btnSecondary}>Watch a rescue in 20 seconds</a>
        </div>
        <PhoneStage />
      </div>
      <Backdrop />
    </section>
  );
}

"use client";

// The close: what AI does and does not do, the thirty-second way to try it, the questions people ask, and the
// last call to action. Then the footer, which also carries the sign-out for whoever is signed in.

import { ArrowRight, HelpingHand, LayoutDashboard, Mic, Plus } from "lucide-react";
import { useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import type { Me } from "@/lib/api";
import { signOut } from "@/lib/session";

import { btnPrimary, btnSecondary, deskHref, Em, H2, Landscape, openDesk, panel } from "./parts";

/* ---------------------------------------------------------------- try it: three connected steps */

export function Try({ me }: { me?: Me | null }) {
  const steps = [
    { icon: Mic, title: "Ask for help", body: "Open the help page on a phone and speak or type a request.", href: "/r", cta: "Open the help page", desk: false },
    { icon: LayoutDashboard, title: "Watch it land", body: "It appears on the national desk within seconds. Send a team.", href: deskHref(me), cta: "Open the desk", desk: true },
    { icon: HelpingHand, title: "Answer as the team", body: "Accept, reach them, count who came out. Then the family is asked.", href: "/responder", cta: "Open the team app", desk: false },
  ];
  return (
    <section id="try" aria-labelledby="try-h" className="mx-auto max-w-7xl scroll-mt-24 px-4 sm:px-6">
      <div className={`rv relative overflow-hidden ${panel} px-5 py-12 sm:px-10 lg:px-14 lg:py-16`}>
        <div aria-hidden className="lp-grid absolute inset-0 opacity-50" />
        <div className="relative">
          <div className="max-w-xl">
            <H2><span id="try-h">Try the whole rescue</span> <Em>in 30 seconds.</Em></H2>
            <p className="mt-3 text-[1.0625rem] text-ink-2">Three screens, one family. The same real code runs on all of them.</p>
          </div>
          <ol className="relative mt-10 grid gap-6 md:grid-cols-3 md:gap-8">
            <span aria-hidden className="absolute left-[2.1rem] top-6 hidden h-px w-[calc(100%-4.2rem)] bg-[linear-gradient(90deg,var(--lp-accent)_0,var(--lp-accent)_50%,transparent_50%)] bg-[length:10px_1px] opacity-40 md:block" />
            {steps.map((s, i) => (
              <li key={s.title} className="relative flex flex-col">
                <span className="relative z-10 grid size-12 place-items-center rounded-full bg-ink text-paper shadow-[var(--shadow-card)]"><s.icon className="size-5" aria-hidden /></span>
                <p className="tabular mt-5 text-small font-semibold text-[var(--lp-accent)]">Step {i + 1}</p>
                <h3 className="mt-1 text-xl font-semibold tracking-[-0.02em]">{s.title}</h3>
                <p className="mt-1.5 flex-1 text-[0.9375rem] leading-relaxed text-ink-2">{s.body}</p>
                <a href={s.href} onClick={s.desk ? openDesk : undefined} className={`${i === 0 ? btnPrimary : btnSecondary} mt-5 self-start`}>
                  {s.cta}<ArrowRight className="size-4" aria-hidden />
                </a>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- FAQ: an accordion that opens smoothly */

const FAQS: [string, string][] = [
  ["Which disasters is it for?", "Any of them: floods, cyclones, landslides, fires, building collapses and accidents. Each disaster is an incident with its own districts, and every kind of team (fire, rescue, medical, volunteer groups) is handled the same way: one owner per case, followed to the family’s confirmation."],
  ["What is RakshaSetu?", "A district control room’s rescue-request desk for the first two weeks of a disaster. It turns reports from calls, voice clips, forwards and spreadsheets into one case per family, gives each one rescue team, and follows it until the family confirms they are safe."],
  ["Does AI decide who gets rescued?", "No. AI only turns speech into text and pulls out facts with the exact words they came from. Priority comes from rules, and matching, assigning and closing are done by people."],
  ["Can someone ask for help without an account?", "Yes. The help page needs no sign-in, password or code. Anyone can speak or type from a phone, including a relative far away."],
  ["How does it find people without a GPS pin?", "It reads landmarks in the message, like “behind the primary school”, and matches them to OpenStreetMap places to draw an honest circle of about 150 m, rather than pretending to know the exact spot."],
  ["Which languages does it understand?", "Voice is transcribed by Sarvam, which is built for Indian languages and detects the language itself. Hindi, Hinglish, Marathi and English are also read by plain word rules, with no AI needed. Other Indian languages are read when the AI keys are set, and always become a case with the original words kept, so a person can read or hear them. Screens are in English for now."],
  ["What if a rescue team goes quiet?", "The desk shows it as “not heard from” and the duty officer decides. The case is never moved to another team automatically."],
  ["Can people report on WhatsApp?", "Forwarded WhatsApp messages are read today: a volunteer pastes them into the desk, or a partner sends them through the signed interface, and they join the right family. A live WhatsApp number that a family can message directly is designed and the server is shaped for it, but it is not switched on yet."],
  ["What if there is no signal?", "On the help page, a request is saved on the phone and sent by itself when signal returns, and it can be handed to someone nearby to forward. A phone-to-phone Bluetooth relay is designed but not built: the animation on the no-signal page is a simulation and says so."],
  ["Is the data real?", "The people and phone numbers are made up. The places are real OpenStreetMap data, and the demo clock runs 60 times faster and is labelled."],
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section id="faq" aria-labelledby="faq-h" className="mx-auto max-w-3xl scroll-mt-24 px-4 py-20 sm:px-6 lg:py-28">
      <div className="rv text-center">
        <H2><span id="faq-h">You’ve got questions.</span> <Em>We’ve got answers.</Em></H2>
      </div>
      <ul className="rv mt-10 divide-y divide-ink/10 border-y border-ink/10">
        {FAQS.map(([q, a], i) => {
          const on = open === i;
          return (
            <li key={q}>
              <button type="button" aria-expanded={on} aria-controls={`faq-${i}`} onClick={() => setOpen(on ? null : i)}
                      className="flex w-full items-center justify-between gap-4 py-5 text-left text-[1.0625rem] font-semibold tracking-[-0.01em]">
                {q}
                <span className={`grid size-8 shrink-0 place-items-center rounded-full transition-[transform,background-color] duration-300 ${on ? "rotate-45 bg-ink text-paper" : "bg-ink/[0.06]"}`}><Plus className="size-4" aria-hidden /></span>
              </button>
              <div id={`faq-${i}`} role="region" className="lp-acc" data-open={on}>
                <div><p className="pb-5 pr-12 text-[0.9375rem] leading-relaxed text-ink-2">{a}</p></div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/* ---------------------------------------------------------------- the last call to action */

export function Final({ me }: { me?: Me | null }) {
  return (
    <section className="px-3 pb-3 sm:px-5 sm:pb-5">
      <div className="lp-sunrise relative mx-auto max-w-7xl overflow-hidden rounded-[32px] border border-line px-5 pb-56 pt-16 text-center sm:px-10 sm:pb-64 lg:pt-24">
        <div className="relative z-10 mx-auto max-w-2xl">
          <Mark className="mx-auto size-12" />
          <h2 className="mt-5 text-[2rem] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-5xl">Be the <Em>bridge</Em> that gets a family home.</h2>
          <p className="mt-4 text-[1.0625rem] text-ink-2">Ask for help from a phone, watch it land on the desk, and follow it to the family’s confirmation.</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href="/r" className={btnPrimary}>I need help<ArrowRight className="size-4" aria-hidden /></a>
            <a href={deskHref(me)} onClick={openDesk} className={btnSecondary}>Open the control room</a>
          </div>
        </div>
        <Landscape className="pointer-events-none absolute inset-x-0 bottom-0 h-56 w-full sm:h-64" />
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- footer */

export function Footer({ me }: { me?: Me | null }) {
  return (
    <footer className="mx-auto max-w-7xl px-4 pb-10 pt-10 sm:px-6">
      <div className="flex flex-col justify-between gap-8 md:flex-row">
        <div className="max-w-sm">
          <p className="flex items-center gap-2.5"><Mark className="size-7" /><span className="text-[1.0625rem] font-semibold tracking-tight">RakshaSetu</span></p>
          <p className="mt-3 text-[0.9375rem] text-ink-2">“Bridge of protection”. A district rescue desk that keeps every family’s case together until they are safe.</p>
        </div>
        <div className="grid grid-cols-2 gap-x-14 gap-y-6 text-[0.9375rem]">
          <div>
            <p className="text-small font-semibold text-ink-3">Open</p>
            <ul className="mt-3 space-y-2">
              <li><a className="hover:underline" href="/r">Ask for help</a></li>
              <li><a className="hover:underline" href="/responder">Team app</a></li>
              <li><a className="hover:underline" href="/login" onClick={openDesk}>Control room</a></li>
              <li><a className="hover:underline" href="/mesh">No signal? How it works</a></li>
            </ul>
          </div>
          <div>
            <p className="text-small font-semibold text-ink-3">In an emergency</p>
            <ul className="tabular mt-3 space-y-2">
              <li><a className="hover:underline" href="tel:112">112 · Emergency</a></li>
              <li><a className="hover:underline" href="tel:1070">1070 · Disaster helpline</a></li>
              <li><a className="hover:underline" href="tel:1077">1077 · District desk</a></li>
            </ul>
          </div>
        </div>
      </div>
      {me && (
        <p className="mt-8 flex flex-wrap items-center gap-x-3 gap-y-1 text-small text-ink-2">
          Signed in as <b className="font-semibold text-ink">{me.user.name}</b> · {me.user.role_label}
          <button onClick={() => void signOut("/")} className="font-semibold text-ink underline underline-offset-4">Sign out</button>
        </p>
      )}
      <p className="mt-6 border-t border-ink/10 pt-5 text-small text-ink-3">
        Built at CodeAstra 2.0. A demo: every person and phone number is made up, and the demo clock runs 60 times faster.
      </p>
    </footer>
  );
}


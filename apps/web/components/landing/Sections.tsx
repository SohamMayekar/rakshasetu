"use client";

// The middle of the page, in the reference's language: centred headings with a small tag, white cards with soft
// shadows, and tinted icon wells. Every example here is one family and one team, never one kind of disaster.

import {
  ArrowRight, ClipboardList, FileSpreadsheet, Gauge, Globe, HelpingHand, LayoutDashboard, type LucideIcon,
  MessageSquareText, Mic, PhoneCall, ShieldCheck, Users, WifiOff,
} from "lucide-react";

import { delay, Em, H2, openDesk, Tag } from "./parts";

const card = "rounded-[24px] border border-line/80 bg-paper shadow-[var(--shadow-card)]";
const TONES = {
  sky: "bg-sky-100 text-sky-700", amber: "bg-amber-100 text-amber-700", emerald: "bg-emerald-100 text-emerald-700",
  rose: "bg-rose-100 text-rose-700", violet: "bg-violet-100 text-violet-700", slate: "bg-slate-200 text-slate-700",
} as const;
type Tone = keyof typeof TONES;

function Well({ icon: Icon, tone, size = "md" }: { icon: LucideIcon; tone: Tone; size?: "md" | "lg" }) {
  return <span className={`grid shrink-0 place-items-center ${size === "lg" ? "size-12 rounded-2xl" : "size-11 rounded-xl"} ${TONES[tone]}`}><Icon className={size === "lg" ? "size-6" : "size-5"} aria-hidden /></span>;
}

function Head({ tag, children, sub }: { tag?: string; children: React.ReactNode; sub?: string }) {
  return (
    <div className="rv mx-auto max-w-2xl text-center">
      {tag && <Tag>{tag}</Tag>}
      <H2 className={tag ? "mt-4" : ""}>{children}</H2>
      {sub && <p className="mt-3 text-[1.0625rem] text-ink-2">{sub}</p>}
    </div>
  );
}

/* ---------------------------------------------------------------- the problem */

export function Problem() {
  const items: { icon: LucideIcon; tone: Tone; t: string; b: string }[] = [
    { icon: PhoneCall, tone: "sky", t: "Doubled", b: "One family reports five times. Teams go twice, and other families wait." },
    { icon: Users, tone: "amber", t: "Nobody owns it", b: "Two teams to one address, or none, because each thought the other had it." },
    { icon: ClipboardList, tone: "rose", t: "Never confirmed", b: "“Done” is a guess. A quiet team goes unnoticed for hours." },
  ];
  return (
    <section aria-labelledby="problem-h" className="bg-paper py-16 lg:py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Head tag="The problem we solve"><span id="problem-h">In a disaster, help fails in the gaps</span> <Em>between calls, teams and sheets.</Em></Head>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {items.map((it, i) => (
            <div key={it.t} style={delay(i * 90)} className={`rv flex items-start gap-4 p-5 ${card}`}>
              <Well icon={it.icon} tone={it.tone} />
              <div><h3 className="text-heading font-semibold">{it.t}</h3><p className="mt-1 text-body leading-snug text-ink-2">{it.b}</p></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- the three ideas */

function MergeArt() {
  return (
    <div className="relative h-40 overflow-hidden rounded-[18px] bg-wash p-4" aria-hidden>
      {["Daughter · voice", "Neighbour · text", "Sheet · row 118"].map((t, i) => (
        <span key={t} className="lp-chip absolute left-4 rounded-full border border-line bg-paper px-3 py-1 text-small" style={{ top: `${14 + i * 38}px`, animationDelay: `${i * 160}ms` }}>{t}</span>
      ))}
      <span className="lp-case absolute right-4 top-1/2 -translate-y-1/2 rounded-[16px] bg-ink px-3.5 py-3 text-small font-semibold text-paper">1 case<br /><span className="font-normal text-paper/65">CASE-214</span></span>
    </div>
  );
}
function CircleArt() {
  return (
    <div className="relative grid h-40 place-items-center overflow-hidden rounded-[18px] bg-wash" aria-hidden>
      <div className="lp-grid absolute inset-0 opacity-80" />
      <span className="lp-circle absolute size-28 rounded-full border-2 border-dashed border-ink/60 bg-ink/[.06]" />
      <span className="absolute size-2.5 rounded-full bg-ink" />
      <span className="absolute left-[16%] top-[22%] rounded-full bg-paper px-2 py-0.5 text-micro font-semibold shadow-sm">Primary school</span>
      <span className="absolute bottom-[18%] right-[14%] rounded-full bg-paper px-2 py-0.5 text-micro font-semibold shadow-sm">Bridge</span>
    </div>
  );
}
function SilenceArt() {
  return (
    <div className="relative grid h-40 place-items-center overflow-hidden rounded-[18px] bg-wash" aria-hidden>
      <svg viewBox="0 0 80 80" className="absolute size-28 -rotate-90">
        <circle cx="40" cy="40" r="34" fill="none" stroke="rgb(21 21 21 / .12)" strokeWidth="5" />
        <circle className="lp-ring" cx="40" cy="40" r="34" fill="none" stroke="#151515" strokeWidth="5" strokeLinecap="round" strokeDasharray="214" />
      </svg>
      <span className="lp-alarm absolute rounded-md bg-ink px-2 py-1 text-small font-semibold text-paper">Not heard from</span>
      <span className="lp-okay absolute translate-y-10 rounded-md bg-paper px-2 py-1 text-small font-semibold shadow-sm">Team 2 · 30 min</span>
    </div>
  );
}

export function Ideas() {
  const items = [
    { art: <MergeArt />, n: "01", t: "One household, with reasons", b: "Calls, forwards and spreadsheet rows about the same family become one case. Every join shows why, a person can undo it, and a look-alike is shown as “not merged”." },
    { art: <CircleArt />, n: "02", t: "Landmarks become an honest circle", b: "“Behind the primary school, near the bridge” becomes a circle of about 150 m from real map data. We show what we know, never a false pin." },
    { art: <SilenceArt />, n: "03", t: "Silence is noticed, not replaced", b: "One owner per case. If a team goes quiet the desk is told and a person decides. Nothing is reassigned behind anyone’s back." },
  ];
  return (
    <section id="ideas" aria-labelledby="ideas-h" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-20 sm:px-6 lg:py-28">
      <Head tag="Three ideas to remember"><span id="ideas-h">Never lost. Never doubled.</span> <Em>Never stale.</Em></Head>
      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {items.map((it, i) => (
          <article key={it.n} style={delay(i * 100)} className={`rv flex flex-col p-5 transition-shadow duration-300 hover:shadow-[var(--shadow-lift)] ${card}`}>
            {it.art}
            <p className="tabular mt-5 text-small font-semibold text-ink-3">{it.n}</p>
            <h3 className="mt-1 text-heading font-semibold">{it.t}</h3>
            <p className="mt-2 text-body leading-relaxed text-ink-2">{it.b}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- who it is for */

export function Audience() {
  const cards: { icon: LucideIcon; tone: Tone; who: string; body: string; href: string; cta: string; desk?: boolean }[] = [
    { icon: Mic, tone: "sky", who: "Families and people in danger", body: "Speak or type from any phone, in Hindi, English or a mix. No account and no code, then one status page for the family.", href: "/r", cta: "Ask for help" },
    { icon: HelpingHand, tone: "amber", who: "Responding teams and volunteers", body: "Fire, rescue, medical or volunteer: only your own cases, each with one big next step. A wrong tap can be undone.", href: "/responder", cta: "Open the team app" },
    { icon: LayoutDashboard, tone: "emerald", who: "Duty officers and the national desk", body: "Every disaster on one screen. What needs a person is at the top, and the list never re-sorts under the cursor.", href: "/login", cta: "Open the national desk", desk: true },
    { icon: FileSpreadsheet, tone: "rose", who: "Partners and volunteer groups", body: "Bring in a spreadsheet or a partner’s update. Rows join the right families, and nothing is dropped.", href: "/login", cta: "See the desk", desk: true },
  ];
  return (
    <section id="doors" aria-labelledby="doors-h" className="scroll-mt-24 bg-paper py-20 lg:py-28">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Head tag="Built for every stakeholder" sub="One system, each person seeing only what they need."><span id="doors-h">Who is</span> <Em>RakshaSetu</Em> for?</Head>
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c, i) => (
            <a key={c.who} href={c.href} onClick={c.desk ? openDesk : undefined} style={delay(i * 90)}
               className={`rv group flex flex-col p-5 transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[var(--shadow-lift)] ${card}`}>
              <Well icon={c.icon} tone={c.tone} size="lg" />
              <h3 className="mt-5 text-heading font-semibold">{c.who}</h3>
              <p className="mt-2 flex-1 text-body leading-snug text-ink-2">{c.body}</p>
              <span className="mt-5 inline-flex items-center gap-1.5 text-body font-semibold">{c.cta}<ArrowRight className="size-4 transition-transform group-hover:translate-x-1" aria-hidden /></span>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- the brief: what has not been said above */

// Only what the sections above have not already told: the lifecycle, who can see what, every way in (WhatsApp
// next), no signal, sensors, the small role of AI, a record you can check, and calm under load.
export function Brief() {
  const chip = (label: string, icon: LucideIcon, planned = false) => {
    const I = icon;
    return (
      <li key={label} className={`flex items-center gap-2 rounded-full px-3.5 py-2 text-small font-medium ${planned ? "border border-dashed border-ink/30 bg-paper/60 text-ink-2" : "border border-line bg-paper shadow-sm"}`}>
        <I className="size-4 text-[var(--lp-accent)]" aria-hidden />{label}
        {planned && <span className="rounded-full bg-wash px-2 py-0.5 text-micro font-semibold uppercase tracking-wider text-ink-2">Planned</span>}
      </li>
    );
  };
  const single: { icon: LucideIcon; tone: Tone; t: string; b: string; note?: string; href?: string }[] = [
    { icon: Globe, tone: "sky", t: "Incident lifecycle", b: "Draft, active, standing down, closed. A new disaster is a form, with its own districts and case numbers." },
    { icon: ShieldCheck, tone: "emerald", t: "Roles and trust", b: "Eight roles, limited in the database itself, so a district officer never sees another state. Partner calls are signed and cannot be replayed." },
    { icon: WifiOff, tone: "slate", t: "Works with no signal", b: "A request is saved on the phone and sent by itself when signal returns. A phone-to-phone relay is designed.", note: "Saving works today", href: "/mesh" },
    { icon: Gauge, tone: "amber", t: "Live sensors", b: "A partner’s instruments report signed readings beside the families they may affect. They never change a priority.", note: "Simulated in the demo" },
    { icon: MessageSquareText, tone: "violet", t: "AI, kept small", b: "AI turns speech into text and pulls out facts with their exact quotes. Rules rank, every reason shown, and people decide." },
    { icon: ClipboardList, tone: "rose", t: "A record you can check", b: "Voice clips, photos and messages are kept by fingerprint, and every step is on a tamper-evident trail with one button to check it." },
    { icon: Users, tone: "sky", t: "Calm under load", b: "Updates arrive live. Dozens of reports at once become a short list of what needs a person, and the list never jumps under the cursor." },
  ];
  return (
    <section id="brief" aria-labelledby="brief-h" className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
      <Head tag="Built for the brief" sub="What the problem statement asks for beyond the story above, each one a screen you can open."><span id="brief-h">An incident command layer,</span> <Em>point by point.</Em></Head>
      <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* every way in, with WhatsApp as the next one */}
        <article className={`rv flex flex-col p-6 md:col-span-2 ${card} bg-gradient-to-br from-paper to-[var(--lp-wash)]`}>
          <div className="flex items-start gap-4">
            <Well icon={PhoneCall} tone="emerald" size="lg" />
            <div>
              <h3 className="text-xl font-semibold tracking-[-0.01em]">Many ways in, one stream of cases</h3>
              <p className="mt-1.5 max-w-xl text-body leading-relaxed text-ink-2">
                However a report arrives, it is read the same way, joined to the right family and kept with its source.
                A live WhatsApp number is designed next: a family messages a number they already know.
              </p>
            </div>
          </div>
          <ul className="mt-6 flex flex-wrap gap-2" aria-label="Ways a report arrives">
            {chip("Voice message", Mic)}
            {chip("Typed call", PhoneCall)}
            {chip("Forwarded text", MessageSquareText)}
            {chip("Volunteer sheet", FileSpreadsheet)}
            {chip("Partner interface", ShieldCheck)}
            {chip("WhatsApp number", MessageSquareText, true)}
          </ul>
        </article>
        {single.map((x, i) => (
          <article key={x.t} style={delay((i % 3) * 80)} className={`rv flex flex-col p-5 ${card}`}>
            <Well icon={x.icon} tone={x.tone} />
            <h3 className="mt-4 text-heading font-semibold">{x.t}</h3>
            <p className="mt-1.5 flex-1 text-body leading-snug text-ink-2">{x.b}</p>
            {(x.note || x.href) && (
              <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-small">
                {x.note && <span className="rounded-full bg-wash px-2.5 py-0.5 font-medium text-ink-2">{x.note}</span>}
                {x.href && <a href={x.href} className="inline-flex items-center gap-1 font-semibold text-[var(--lp-accent)] underline underline-offset-4">See it work<ArrowRight className="size-3.5" aria-hidden /></a>}
              </p>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

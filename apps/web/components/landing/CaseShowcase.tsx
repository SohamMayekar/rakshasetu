"use client";

import { Check, ShieldCheck, Siren, AudioLines, MessageSquareText, FileSpreadsheet, Radio } from "lucide-react";
import Link from "next/link";

import { ArrowUpRightIcon, ArrowRightIcon } from "@/components/landing/icons";
import { SectionHeader } from "@/components/landing/SectionHeader";
import { Mark } from "@/components/shell/Sidebar";
import { useReveal } from "@/hooks/use-reveal";

const CHANNELS = [
  { icon: AudioLines, title: "A voice call", detail: "Spoken Hindi or English audio from a stranded family" },
  { icon: MessageSquareText, title: "Forwarded message", detail: "Neighbours or relatives forwarding WhatsApp distress text" },
  { icon: FileSpreadsheet, title: "Volunteer sheets", detail: "Hundreds of field survey rows parsed simultaneously" },
  { icon: Radio, title: "Partner radio logs", detail: "Police or civil defence teams sharing coordinate updates" },
];

export function CaseShowcase() {
  const { ref: headerRef } = useReveal<HTMLDivElement>();
  const { ref: stripRef } = useReveal<HTMLDivElement>();
  const { ref: caseRef } = useReveal<HTMLDivElement>();

  return (
    <section id="case-study" aria-labelledby="case-heading" className="section section-top bg-white">
      <div ref={headerRef} className="container-site">
        <SectionHeader
          headingId="case-heading"
          tag="REAL-TIME CASE DOSSIER"
          heading="From fragmented panic to one verifiable rescue."
          body="Disaster reports arrive in fragments across WhatsApp forwards, calls, and spreadsheets. RakshaSetu clusters them into a single accountable case dossier that officers and rescue crews follow to safety."
        />
      </div>

      {/* 1. Multi-Channel Intake Strip */}
      <div ref={stripRef} className="container-site mb-12">
        <div data-reveal="" className="rounded-3xl border border-hairline bg-surface p-6 md:p-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-hairline">
            <div>
              <span className="text-[11px] font-bold tracking-widest text-slate uppercase">MULTI-CHANNEL INTAKE</span>
              <h3 className="mt-1 font-display text-xl font-bold text-ink">Every channel flows into one desk</h3>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3.5 py-1.5 text-[12px] font-semibold text-slate border border-hairline shadow-sm">
              <span className="size-2 rounded-full bg-[#15803d]" />
              Zero duplicate dispatches
            </span>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CHANNELS.map(({ icon: Icon, title, detail }, i) => (
              <div
                key={title}
                className="flex items-start gap-3.5 rounded-2xl bg-white p-4.5 border border-hairline shadow-sm"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-surface text-ink">
                  <Icon className="size-5" />
                </span>
                <div>
                  <h4 className="text-body font-bold text-ink">{title}</h4>
                  <p className="mt-1 text-caption text-slate leading-snug">{detail}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Convergence Callout */}
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl bg-ink p-4 md:p-5 text-white">
            <div className="flex items-center gap-3">
              <span className="grid size-9 place-items-center rounded-xl bg-white/10 text-white">
                <Mark className="size-5" />
              </span>
              <div>
                <p className="text-body font-bold">Converged into One Family Dossier</p>
                <p className="text-caption text-white/70">Automatic matching by phone numbers, landmarks, and family surnames</p>
              </div>
            </div>
            <Link
              href="/login"
              className="group inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-caption font-bold text-ink hover:bg-surface transition-colors shrink-0"
            >
              <span>View live desk</span>
              <ArrowUpRightIcon className="size-3.5 transition-transform group-hover:rotate-45" />
            </Link>
          </div>
        </div>
      </div>

      {/* 2. Interactive Case Dossier Frame */}
      <div ref={caseRef} className="container-site">
        <div
          data-reveal=""
          className="overflow-hidden rounded-3xl border border-hairline bg-white shadow-[0_24px_64px_-24px_rgba(8,11,15,0.18)]"
        >
          {/* Card Top Rail */}
          <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-hairline bg-surface/50">
            <div className="flex items-center gap-2.5">
              <span className="grid size-7 place-items-center rounded-lg bg-ink text-white">
                <Mark className="size-4" />
              </span>
              <span className="font-display text-body-sm font-bold text-ink">Case #BR-GOP-0482</span>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-[11px] font-semibold text-slate border border-hairline shadow-sm">
              <span className="size-2 rounded-full bg-[#15803d]" />
              Synthetic demonstration case
            </span>
          </div>

          {/* Card Body: Split Schematic Map & Fact Dossier */}
          <div className="grid lg:grid-cols-12 min-h-[420px]">
            {/* Left: Schematic Flood Radar Map */}
            <div className="relative overflow-hidden bg-[#e6ebec] lg:col-span-7 min-h-[320px] lg:min-h-full">
              <svg viewBox="0 0 700 420" preserveAspectRatio="xMidYMid slice" className="size-full">
                {/* River water currents */}
                <path
                  d="M-40 60 C 120 80, 160 140, 280 120 C 400 100, 440 40, 560 60 C 660 80, 720 120, 780 90 L 780 240 C 650 200, 560 230, 460 260 C 320 300, 200 240, -40 270 Z"
                  fill="#b9d5dc"
                  opacity="0.8"
                />
                {/* Road networks */}
                <path d="M-20 340 C 120 260, 220 180, 360 190 C 500 200, 600 120, 740 90" fill="none" stroke="#f4f5f1" strokeWidth="14" />
                <path d="M-20 340 C 120 260, 220 180, 360 190 C 500 200, 600 120, 740 90" fill="none" stroke="#d5dad7" strokeWidth="2" strokeDasharray="6 6" />
                <path d="M120 -20 C 160 120, 140 220, 240 320 C 320 400, 420 440, 500 460" fill="none" stroke="#f4f5f1" strokeWidth="8" />
                
                {/* Search Area Radius Circle */}
                <circle cx="390" cy="210" r="96" fill="rgba(37,99,235,0.08)" stroke="#2563eb" strokeWidth="2" strokeDasharray="6 8" />
                <circle cx="390" cy="210" r="24" fill="none" stroke="#2563eb" strokeWidth="1.5" opacity="0.4" className="animate-ping origin-center" />
                <circle cx="390" cy="210" r="8" fill="#1e3a8a" stroke="#ffffff" strokeWidth="3" />
                <circle cx="390" cy="210" r="16" fill="rgba(30,58,138,0.2)" />
              </svg>

              {/* Floating map tags */}
              <div className="absolute top-4 left-4 rounded-xl bg-white/90 backdrop-blur-md px-3.5 py-2 text-[12px] font-bold text-ink shadow-sm border border-black/5">
                <span>Thawe, Gopalganj</span>
                <span className="block text-[11px] font-normal text-slate">OSM Landmark Search Perimeter</span>
              </div>
              <div className="absolute bottom-4 left-4 rounded-xl bg-ink/90 text-white backdrop-blur-md px-3.5 py-2 text-[11px] font-medium shadow-sm">
                <span>Estimated Search Radius: 650m</span>
              </div>
            </div>

            {/* Right: Detailed Fact Dossier */}
            <div className="flex flex-col justify-between p-6 md:p-8 lg:col-span-5 bg-white">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-bold tracking-widest text-[#c62828] uppercase">P1 · RESCUE IN PROGRESS</span>
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-[#15803d]/10 px-2.5 py-1 text-[11px] font-bold text-[#15803d]">
                    <Check className="size-3" />
                    Confirmed Safe
                  </span>
                </div>

                <h3 className="mt-3 font-display text-2xl font-bold tracking-tight text-ink">
                  Choudhary Household · 6 Persons
                </h3>

                {/* Verbatim quote */}
                <div className="mt-4 rounded-2xl bg-surface p-4 border border-hairline">
                  <p className="text-[11px] font-bold text-slate uppercase tracking-wider">Caller Verbatim Words</p>
                  <blockquote className="mt-1.5 font-accent text-lg italic text-ink leading-snug">
                    “Pani chhat tak aa gaya hai. 6 log hain, dadi chal nahi sakti. Please jaldi aao.”
                  </blockquote>
                  <p className="mt-2 text-[12px] text-slate-light">
                    Translated: “Water has reached the roof. 6 people, grandmother cannot walk. Please come fast.”
                  </p>
                </div>

                {/* Facts Table */}
                <div className="mt-5 grid grid-cols-2 gap-3 text-body-sm">
                  <div className="rounded-xl border border-hairline p-3">
                    <span className="text-[11px] text-slate">People Reported</span>
                    <p className="mt-0.5 text-base font-bold text-ink">6 (1 Infant, 1 Elderly)</p>
                  </div>
                  <div className="rounded-xl border border-hairline p-3">
                    <span className="text-[11px] text-slate">Assigned Crew</span>
                    <p className="mt-0.5 text-base font-bold text-ink">Fire & Boat 5</p>
                  </div>
                  <div className="rounded-xl border border-hairline p-3">
                    <span className="text-[11px] text-slate">Silence Watchdog</span>
                    <p className="mt-0.5 text-base font-bold text-[#15803d]">Active · Checked 4m ago</p>
                  </div>
                  <div className="rounded-xl border border-hairline p-3">
                    <span className="text-[11px] text-slate">Family Sign-off</span>
                    <p className="mt-0.5 text-base font-bold text-[#15803d]">Verified via SMS link</p>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-6 pt-5 border-t border-hairline flex items-center justify-between gap-3">
                <Link
                  href="/r"
                  className="inline-flex items-center gap-1.5 text-caption font-bold text-ink hover:underline"
                >
                  <span>Test reporting page</span>
                  <ArrowRightIcon className="size-3.5" />
                </Link>
                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-4 py-2 text-caption font-bold text-white hover:bg-ink-soft transition-colors"
                >
                  <span>Open control room</span>
                  <ArrowUpRightIcon className="size-3" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

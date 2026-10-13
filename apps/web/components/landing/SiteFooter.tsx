"use client";

import Link from "next/link";
import { ArrowUp, Phone, ShieldCheck, HeartHandshake } from "lucide-react";

import { Cta } from "@/components/landing/Cta";
import { ArrowUpRightIcon } from "@/components/landing/icons";
import { Mark } from "@/components/shell/Sidebar";
import { SlotImage } from "@/components/landing/SlotImage";
import { footerContent } from "@/components/landing/content";
import { useGsap } from "@/hooks/use-gsap";
import { useReveal } from "@/hooks/use-reveal";

const FOOTER_FRAME = {
  gap: { mobile: 12, desktop: 20 },
  radius: 30,
  start: "top 60%",
};

export function SiteFooter() {
  const { ref: ctaRef } = useReveal<HTMLDivElement>();
  const { ref: bodyRef } = useReveal<HTMLDivElement>();

  const { ref: footerRef } = useGsap<HTMLElement>(({ el, q, isMobile, gsap }) => {
    const g = isMobile ? FOOTER_FRAME.gap.mobile : FOOTER_FRAME.gap.desktop;
    const frame = q("[data-footer-frame]")[0];
    if (frame) {
      gsap.fromTo(
        frame,
        { clipPath: `inset(${g}px ${g}px ${g}px ${g}px round ${FOOTER_FRAME.radius}px)` },
        {
          clipPath: "inset(0px 0px 0px 0px round 0px)",
          ease: "none",
          scrollTrigger: {
            trigger: el,
            start: FOOTER_FRAME.start,
            end: "bottom bottom",
            scrub: 0.35,
            invalidateOnRefresh: true,
            onRefresh: (self) => {
              self.animation?.progress(self.progress);
            },
          },
        },
      );
    }

    const photo = q("[data-footer-photo]")[0];
    const mark = q("[data-wordmark]")[0];
    const drift = isMobile ? 35 : 85;

    if (photo && mark) {
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: el,
          start: "top bottom",
          end: "bottom bottom",
          scrub: true,
          invalidateOnRefresh: true,
        },
      });
      tl.fromTo(photo, { y: -drift, scale: 1.12 }, { y: drift, scale: 1.12, ease: "none" }, 0)
        .fromTo(mark, { y: drift * 0.4 }, { y: -drift * 0.4, ease: "none" }, 0);
    }
  });

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <footer ref={footerRef} className="relative bg-white pt-10">
      <div
        data-footer-frame=""
        className="relative overflow-hidden bg-ink text-white will-change-[clip-path] [clip-path:inset(12px_12px_12px_12px_round_30px)] md:[clip-path:inset(20px_20px_20px_20px_round_30px)]"
      >
        {/* Upper Cinematic Panel with Big CTA and Drifting Wordmark */}
        <div className="relative flex min-h-[580px] md:min-h-[680px] flex-col justify-between overflow-hidden px-6 pt-16 pb-12 md:px-12 md:pt-24">
          <div data-footer-photo="" className="absolute inset-0 will-change-transform">
            <SlotImage
              slot="footer.photo"
              sizes="100vw"
              tone="dark"
              imageClassName="object-center"
            />
          </div>

          {/* Gradients */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-b from-ink/80 via-ink/60 to-ink"
          />

          {/* Top closing CTA */}
          <div ref={ctaRef} className="container-site relative z-10 mx-auto max-w-4xl text-center">
            <span
              data-reveal="fade"
              className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-caption font-semibold backdrop-blur-md"
            >
              <HeartHandshake className="size-4 text-[#cadccf]" />
              National Emergency Readiness
            </span>

            <h2
              data-reveal=""
              className="mt-6 font-display text-display-lg md:text-display-xl font-bold tracking-tight text-white leading-tight"
            >
              Every request deserves<br />
              <span className="font-accent italic font-normal text-[#d6e1da]">a clear next step.</span>
            </h2>

            <p
              data-reveal=""
              className="mx-auto mt-4 max-w-xl text-body-lg text-white/85 leading-relaxed"
            >
              Ask for help immediately, or open the universal district control room that connects citizen reports with the teams who answer.
            </p>

            <div
              data-reveal=""
              className="mt-8 flex flex-wrap items-center justify-center gap-3.5"
            >
              <Cta href="/r" tone="light" arrow magnetic shape="pill">
                I need help (Citizen)
              </Cta>
              <Cta href="/login" tone="glass" shape="pill">
                Open Control Room
              </Cta>
              <Cta href="/responder" tone="glass" shape="pill">
                Responder App
              </Cta>
            </div>
          </div>

          {/* Gigantic Drifting Background Wordmark */}
          <div
            data-wordmark=""
            aria-hidden="true"
            className="pointer-events-none relative z-10 w-full overflow-hidden text-center will-change-transform pt-12 select-none"
          >
            <span className="block font-display text-wordmark font-bold tracking-tighter text-white/10 leading-none">
              RAKSHASETU
            </span>
          </div>
        </div>

        {/* Lower Luxury Footer Columns */}
        <div ref={bodyRef} className="border-t border-white/15 bg-[#05080c] px-6 py-12 md:px-12 md:py-16">
          <div className="container-site mx-auto grid gap-10 md:grid-cols-2 lg:grid-cols-12">
            {/* Brand Column */}
            <div className="lg:col-span-5 space-y-4">
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-xl bg-white text-ink">
                  <Mark className="size-5" />
                </span>
                <span className="font-display text-xl font-bold text-white">RakshaSetu</span>
              </div>
              <p className="max-w-sm text-body-sm text-white/70 leading-relaxed">
                {footerContent.summary}
              </p>
              <div className="flex items-center gap-2 pt-2 text-[12px] text-white/50">
                <ShieldCheck className="size-4 text-[#cadccf]" />
                <span>Deterministic rule triage · Quote-backed fact provenance</span>
              </div>
            </div>

            {/* Emergency Hotlines Column */}
            <div className="lg:col-span-4 space-y-3">
              <p className="text-[11px] font-bold tracking-widest text-white/50 uppercase">
                Official Emergency Helplines
              </p>
              <div className="space-y-2">
                {footerContent.hotlines.map((h) => (
                  <div
                    key={h.number}
                    className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-body-sm"
                  >
                    <span className="text-white/80">{h.label}</span>
                    <a
                      href={`tel:${h.number}`}
                      className="font-display font-bold text-white hover:text-[#cadccf] flex items-center gap-1.5"
                    >
                      <Phone className="size-3.5" />
                      {h.number}
                    </a>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Links Column */}
            <div className="lg:col-span-3 space-y-3">
              <p className="text-[11px] font-bold tracking-widest text-white/50 uppercase">
                Direct Portals
              </p>
              <ul className="space-y-2 text-body-sm font-semibold">
                {footerContent.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="flex items-center justify-between text-white/80 hover:text-white transition-colors"
                    >
                      <span>{link.label}</span>
                      <ArrowUpRightIcon className="size-3.5 text-white/40" />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Bottom Copyright & Disclaimer */}
          <div className="container-site mx-auto mt-12 pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4 text-[12px] text-white/50">
            <p>© 2026 RakshaSetu · All demonstration people, phone numbers and cases are synthetic.</p>
            <div className="flex items-center gap-4">
              <span>Map data © OpenStreetMap</span>
              <button
                type="button"
                onClick={scrollToTop}
                aria-label="Back to top"
                className="grid size-8 place-items-center rounded-full border border-white/20 bg-white/10 text-white hover:bg-white hover:text-ink transition-colors"
              >
                <ArrowUp className="size-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

"use client";

import Link from "next/link";
import { ChevronDown, Siren, ShieldCheck } from "lucide-react";

import { Cta } from "@/components/landing/Cta";
import { ArrowUpRightIcon } from "@/components/landing/icons";
import { SlotImage } from "@/components/landing/SlotImage";
import { hero } from "@/components/landing/content";
import { useGsap } from "@/hooks/use-gsap";
import { useReveal } from "@/hooks/use-reveal";
import { frameHero } from "@/lib/hero-frame";
import { SplitWords } from "@/lib/split-text";

const PARALLAX = 0.22;
const PARALLAX_TRAVEL = 1400;

export function Hero() {
  const { ref: contentRef } = useReveal<HTMLDivElement>({ immediate: true });
  const { ref: railRef } = useReveal<HTMLDivElement>({ immediate: true });

  const { ref: stageRef } = useGsap<HTMLElement>(({ el, q, isMobile, gsap }) => {
    const photoWrap = q("[data-hero-photo]")[0];
    const frame = q("[data-hero-frame]")[0];
    if (frame) frameHero(gsap, frame, el, isMobile);

    if (photoWrap) {
      const rate = isMobile ? PARALLAX / 2 : PARALLAX;
      gsap.to(photoWrap, {
        y: PARALLAX_TRAVEL * rate,
        scale: 1 + PARALLAX_TRAVEL / 14000,
        ease: "none",
        scrollTrigger: {
          trigger: el,
          start: "top top",
          end: `+=${PARALLAX_TRAVEL}`,
          scrub: true,
          invalidateOnRefresh: true,
        },
      });
    }
  });

  return (
    <section
      ref={stageRef}
      id="top"
      aria-labelledby="hero-heading"
      className="relative bg-white"
    >
      <div
        data-hero-frame=""
        className="relative flex min-h-[100svh] min-h-[660px] flex-col overflow-hidden bg-ink will-change-[clip-path] md:min-h-[740px]"
      >
        {/* Parallax Background Photo Container */}
        <div data-hero-photo="" className="absolute inset-0 will-change-transform">
          <div data-hero-image="" className="photo-settle absolute inset-0">
            <SlotImage
              slot="home.hero"
              sizes="100vw"
              priority
              tone="dark"
              imageClassName="object-[center_35%]"
            />
          </div>
        </div>

        {/* Cinematic Disaster Operation Atmosphere Overlays */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#080b0f]/60 via-[#080b0f]/35 to-[#080b0f]/80"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_90%_50%_at_50%_45%,rgba(8,11,15,0.48),transparent_80%)]"
        />

        {/* Hero Topographic Water Current Lines */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-20 mix-blend-screen"
        >
          <svg viewBox="0 0 1600 1000" className="size-full" preserveAspectRatio="none">
            <path
              d="M-50 400 C 300 250, 600 550, 1000 350 C 1300 200, 1500 450, 1700 380"
              fill="none"
              stroke="#cadccf"
              strokeWidth="1.5"
              strokeDasharray="6 8"
            />
            <path
              d="M-50 480 C 280 330, 650 620, 1050 420 C 1350 280, 1480 520, 1700 450"
              fill="none"
              stroke="#cfe3ef"
              strokeWidth="1.2"
            />
          </svg>
        </div>

        {/* Centered Hero Editorial Content */}
        <div
          ref={contentRef}
          className="relative z-10 mx-auto flex w-full max-w-[1320px] flex-1 flex-col items-center justify-center px-6 pt-[clamp(7rem,16vh,10.5rem)] pb-12 text-center"
        >
          {/* Eyebrow Pill */}
          <span
            data-reveal="fade"
            className="inline-flex h-8 items-center gap-2.5 rounded-full border border-white/25 bg-white/10 px-4 text-caption font-semibold text-white shadow-sm backdrop-blur-md"
          >
            <span aria-hidden="true" className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-[#cadccf]/80" />
              <span className="relative inline-flex size-2 rounded-full bg-[#cadccf]" />
            </span>
            <span>{hero.eyebrow}</span>
          </span>

          {/* Master Headline */}
          <h1
            id="hero-heading"
            className="mt-8 max-w-[22ch] text-balance font-display text-[clamp(2.4rem,8.5vw,4.8rem)] font-bold leading-[1.04] tracking-[-0.038em] text-white [text-shadow:0_4px_30px_rgba(8,11,15,0.45)] min-[900px]:max-w-none"
          >
            <span className="block">
              <SplitWords text={hero.headingLines[0]} reveal />
            </span>
            <span className="block font-accent text-[1.12em] font-normal italic tracking-[-0.01em] text-[#d6e1da]">
              <SplitWords text={hero.headingLines[1]} reveal offset={hero.headingLines[0].split(/\s+/).length} />
            </span>
          </h1>

          {/* Lede paragraph */}
          <p
            data-reveal=""
            style={{ ["--delay" as string]: "280ms" }}
            className="mt-6 max-w-[36rem] text-balance text-body-lg text-white/90 [text-shadow:0_2px_18px_rgba(8,11,15,0.55)] md:text-lead"
          >
            {hero.body}
          </p>

          {/* Hero CTAs */}
          <div
            data-reveal=""
            style={{ ["--delay" as string]: "340ms" }}
            className="mt-9 flex flex-wrap items-center justify-center gap-3.5"
          >
            <Cta href={hero.primaryCta.href} tone="light" arrow magnetic shape="pill">
              {hero.primaryCta.label}
            </Cta>
            <Cta href={hero.secondaryCta.href} tone="glass" shape="pill">
              {hero.secondaryCta.label}
            </Cta>
            <Cta href={hero.responderCta.href} tone="glass" shape="pill">
              {hero.responderCta.label}
            </Cta>
          </div>
        </div>

        {/* Bottom Rail: Active Demo Badge on Left, Scroll Indicator on Right */}
        <div
          ref={railRef}
          className="container-site relative z-10 flex items-end justify-between gap-6 pb-6 md:pb-8"
        >
          {/* Active Demo Case Pill Card */}
          <Link
            href="/login"
            data-reveal=""
            style={{ ["--delay" as string]: "500ms" }}
            className="group hidden items-center gap-4 rounded-xl border border-white/20 bg-white/10 py-3 pr-4 pl-4 text-white backdrop-blur-xl transition-all duration-300 hover:bg-white/20 sm:flex"
          >
            <span className="grid size-9 place-items-center rounded-lg bg-white/15 text-[#cadccf]">
              <Siren className="size-4 animate-pulse" />
            </span>
            <div className="flex flex-col text-left">
              <span className="text-[11px] font-semibold tracking-wider text-white/65 uppercase">
                {hero.featured.label}
              </span>
              <span className="mt-0.5 text-body-sm font-semibold tracking-tight text-white">
                {hero.featured.title}
              </span>
            </div>
            <span className="ml-2 grid size-7 place-items-center rounded-full bg-white/10 text-white group-hover:bg-white group-hover:text-ink transition-colors">
              <ArrowUpRightIcon className="arrow-badge size-3.5" />
            </span>
          </Link>

          {/* Scroll cue cue on the right */}
          <a
            href="#how-it-works"
            data-reveal=""
            style={{ ["--delay" as string]: "600ms" }}
            className="group ml-auto flex items-center gap-3 text-caption font-medium text-white/80 transition-colors hover:text-white"
          >
            <span className="hidden sm:inline">Explore how it works</span>
            <span className="grid size-8 place-items-center rounded-full border border-white/25 bg-white/10 backdrop-blur-sm transition-transform group-hover:translate-y-1">
              <ChevronDown className="size-4" />
            </span>
          </a>
        </div>
      </div>
    </section>
  );
}

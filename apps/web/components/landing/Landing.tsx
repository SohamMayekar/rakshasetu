"use client";

import { useEffect, useRef } from "react";

import { SiteNav } from "@/components/landing/SiteNav";
import { Hero } from "@/components/landing/Hero";
import { Metrics } from "@/components/landing/Metrics";
import { Statement } from "@/components/landing/Statement";
import { Services } from "@/components/landing/Services";
import { StackedCards } from "@/components/landing/StackedCards";
import { CaseShowcase } from "@/components/landing/CaseShowcase";
import { Marquee } from "@/components/landing/Marquee";
import { StoryShowcase } from "@/components/landing/StoryShowcase";
import { Faq } from "@/components/landing/Faq";
import { SiteFooter } from "@/components/landing/SiteFooter";
import { loadMotion, prefersReducedMotion } from "@/lib/motion";
import type { Me } from "@/lib/api";

export default function Landing({ me }: { me?: Me | null }) {
  const rootRef = useRef<HTMLDivElement>(null);


  useEffect(() => {
    if (prefersReducedMotion()) return;
    let cancelled = false;
    let destroy: (() => void) | undefined;

    Promise.all([loadMotion(), import("lenis")]).then(([{ gsap, ScrollTrigger }, { default: Lenis }]) => {
      if (cancelled) return;
      const lenis = new Lenis({
        duration: 1.1,
        easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smoothWheel: true,
        touchMultiplier: 1.5,
      });

      lenis.on("scroll", ScrollTrigger.update);
      const tick = (time: number) => lenis.raf(time * 1000);
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);

      // Handle smooth hash anchor scrolling
      const handleAnchorClick = (e: MouseEvent) => {
        const target = e.target as HTMLElement;
        const anchor = target.closest<HTMLAnchorElement>("a[href*='#']");
        if (!anchor) return;
        const href = anchor.getAttribute("href");
        if (!href) return;
        const hash = href.startsWith("#") ? href : href.slice(href.indexOf("#"));
        if (hash === "#" || hash === "#top") {
          e.preventDefault();
          lenis.scrollTo(0, { duration: 1.2 });
        } else {
          const el = document.querySelector(hash);
          if (el) {
            e.preventDefault();
            lenis.scrollTo(el as HTMLElement, { offset: -32, duration: 1.2 });
          }
        }
      };

      document.addEventListener("click", handleAnchorClick);

      // Re-measure after fonts load
      document.fonts?.ready.then(() => ScrollTrigger.refresh());

      destroy = () => {
        document.removeEventListener("click", handleAnchorClick);
        gsap.ticker.remove(tick);
        lenis.destroy();
      };
    }).catch(() => {
      // Native scrolling remains active if motion fails
    });

    return () => {
      cancelled = true;
      destroy?.();
    };
  }, []);

  return (
    <div ref={rootRef} className="landing-root relative min-h-screen bg-white">
      <SiteNav me={me} />
      <main id="main-content" className="relative z-10 flex flex-col">
        <Hero />
        <Metrics />
        <Statement />
        <Services />
        <StackedCards />
        <CaseShowcase />
        <Marquee />
        <StoryShowcase />
        <Faq />
      </main>
      <SiteFooter />
    </div>
  );
}

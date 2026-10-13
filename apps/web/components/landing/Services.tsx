"use client";

import { useEffect, useRef } from "react";
import { Check } from "lucide-react";

import { ArrowUpRightIcon } from "@/components/landing/icons";
import { SectionHeader } from "@/components/landing/SectionHeader";
import { SlotImage } from "@/components/landing/SlotImage";
import { pillars, servicesIntro } from "@/components/landing/content";
import { useGsap } from "@/hooks/use-gsap";
import { useReveal } from "@/hooks/use-reveal";
import { prefersReducedMotion } from "@/lib/motion";

const RAIL_SCRUB = 0.8;
const CURVE_DEG = 16;
const CURVE_MAX = 30;

function paintCurve(rail: HTMLElement, active: number) {
  if (prefersReducedMotion()) return;
  Array.from(rail.children).forEach((li, i) => {
    const d = i - active;
    const turn = Math.max(-CURVE_MAX, Math.min(CURVE_MAX, -d * CURVE_DEG));
    (li as HTMLElement).style.transform =
      Math.abs(turn) < 0.01 ? "" : `perspective(1600px) rotateY(${turn.toFixed(2)}deg)`;
  });
}

export function Services() {
  const { ref: headerRef } = useReveal<HTMLDivElement>();
  const { ref: revealRef } = useReveal<HTMLDivElement>({ once: true });
  const railRef = useRef<HTMLUListElement | null>(null);
  const last = pillars.length - 1;

  const { ref: pinRef } = useGsap<HTMLDivElement>(({ el, gsap, ScrollTrigger }) => {
    const rail = railRef.current;
    if (!rail) return;

    const distance = () => {
      const end = rail.lastElementChild as HTMLElement;
      return Math.max(
        0,
        end.offsetLeft + end.offsetWidth + parseFloat(getComputedStyle(rail).paddingRight) - rail.clientWidth,
      );
    };

    gsap.to(rail, {
      x: () => -distance(),
      ease: "none",
      onUpdate() {
        paintCurve(rail, this.progress() * last);
      },
      scrollTrigger: {
        trigger: el,
        start: "center center",
        end: () => `+=${distance()}`,
        pin: true,
        refreshPriority: 1,
        scrub: RAIL_SCRUB,
        anticipatePin: 1,
        invalidateOnRefresh: true,
        snap: {
          snapTo: 1 / last,
          inertia: false,
          duration: { min: 0.35, max: 0.8 },
          delay: 0.08,
          ease: "power3.out",
        },
        onRefresh: (self) => {
          self.animation?.progress(self.progress);
        },
      },
    });

    ScrollTrigger.sort();
    ScrollTrigger.refresh();
    rail.style.overflowX = "visible";
    paintCurve(rail, 0);

    return () => {
      if (rail) rail.style.overflowX = "";
    };
  });

  return (
    <section id="pillars" aria-labelledby="pillars-heading" className="section section-top bg-white">
      <div ref={headerRef} className="container-site">
        <SectionHeader
          headingId="pillars-heading"
          tag={servicesIntro.tag}
          heading={servicesIntro.heading}
          body={servicesIntro.body}
        />
      </div>

      <div ref={pinRef} className="relative w-full overflow-hidden">
        <div ref={revealRef} className="w-full">
          <ul
            ref={railRef}
            className="flex w-max gap-6 px-6 md:px-12 py-8 list-none will-change-transform"
            style={{ transformStyle: "preserve-3d" }}
          >
            {pillars.map((pillar) => (
              <li
                key={pillar.slug}
                data-reveal=""
                className="group relative flex w-[320px] sm:w-[380px] md:w-[440px] shrink-0 flex-col overflow-hidden rounded-2xl border border-hairline bg-surface p-6 md:p-8 transition-all duration-300 hover:border-black/20 hover:shadow-xl"
              >
                {/* Pillar Header Number & Label */}
                <div className="flex items-center justify-between pb-4 border-b border-hairline">
                  <span className="font-display text-2xl font-bold tracking-tight text-ink">
                    {pillar.number}
                  </span>
                  <span className="text-[11px] font-bold tracking-widest text-slate uppercase">
                    PILLAR SPECIFICATION
                  </span>
                </div>

                {/* Card Image Slot */}
                <div className="relative mt-5 aspect-[16/10] w-full overflow-hidden rounded-xl bg-ink/10">
                  <SlotImage
                    slot={pillar.image}
                    sizes="440px"
                    imageClassName="img-zoom"
                  />
                  <div
                    aria-hidden="true"
                    className="absolute inset-0 bg-gradient-to-t from-ink/60 via-transparent to-transparent"
                  />
                </div>

                {/* Title and Summary */}
                <div className="mt-6 flex-1">
                  <h3 className="font-display text-xl font-bold tracking-tight text-ink">
                    {pillar.name}
                  </h3>
                  <p className="mt-3 text-body-sm text-slate leading-relaxed">
                    {pillar.summary}
                  </p>
                </div>

                {/* Key Points */}
                <div className="mt-6 pt-5 border-t border-hairline">
                  <ul className="grid gap-2">
                    {pillar.points.map((pt) => (
                      <li key={pt} className="flex items-center gap-2.5 text-[13px] font-medium text-ink">
                        <span className="grid size-4 shrink-0 place-items-center rounded-full bg-ink text-white">
                          <Check className="size-2.5" />
                        </span>
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

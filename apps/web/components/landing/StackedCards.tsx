"use client";

import { ArrowUpRightIcon } from "@/components/landing/icons";
import { SectionHeader } from "@/components/landing/SectionHeader";
import { SlotImage } from "@/components/landing/SlotImage";
import { stakeholderCards } from "@/components/landing/content";
import { useReveal } from "@/hooks/use-reveal";
import { useScrollProgress } from "@/hooks/use-scroll-progress";
import { cn } from "@/lib/utils";

type Card = (typeof stakeholderCards)[number];

const MIN_SCALE = 0.88;
const LIFT_PX = 28;
const MAX_VEIL = 0.5;

function StackCard({ card, index, isLast }: { card: Card; index: number; isLast: boolean }) {
  const { ref: revealRef } = useReveal<HTMLDivElement>();

  const { ref: runwayRef } = useScrollProgress<HTMLDivElement>(
    (p) => {
      const inner = revealRef.current?.querySelector<HTMLElement>("[data-inner]");
      const veil = revealRef.current?.querySelector<HTMLElement>("[data-veil]");
      if (!inner || !veil) return;
      const s = 1 - p * (1 - MIN_SCALE);
      inner.style.transform = `translate3d(0, ${(-p * LIFT_PX).toFixed(1)}px, 0) scale(${s.toFixed(4)})`;
      veil.style.opacity = (p * MAX_VEIL).toFixed(3);
    },
    { start: "top top", end: "bottom top" },
  );

  return (
    <div
      ref={isLast ? undefined : runwayRef}
      className="sticky top-0 h-svh"
      style={{ zIndex: index + 1 }}
    >
      <div ref={revealRef} className="container-site flex h-full items-center pt-[5.5rem] pb-4 md:pt-24 md:pb-10">
        <article
          data-inner=""
          data-reveal=""
          className="relative flex h-full max-h-[660px] w-full flex-col overflow-hidden rounded-3xl bg-ink shadow-[0_40px_80px_-40px_rgba(8,11,15,0.55)] will-change-transform"
        >
          {/* Card background photo */}
          <div data-reveal-image="" className="absolute inset-0">
            <SlotImage
              slot={card.image}
              sizes="(max-width: 1320px) 100vw, 1320px"
              tone="dark"
              imageClassName="object-center"
            />
          </div>

          {/* Gradients for readability */}
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-b from-[#080b0f]/60 via-[#080b0f]/35 to-[#080b0f]/95"
          />

          {/* Card Header */}
          <div className="relative z-10 flex items-center justify-between p-6 md:p-10">
            <span className="inline-flex h-8 items-center rounded-full border border-white/25 bg-white/10 px-4 text-[12px] font-bold tracking-wider text-white backdrop-blur-md uppercase">
              {card.label}
            </span>
            <span className="text-caption font-semibold text-white/70 tabular-nums">
              {card.index} / 0{stakeholderCards.length}
            </span>
          </div>

          {/* Card Body */}
          <div className="relative z-10 mt-auto grid gap-6 p-6 md:grid-cols-12 md:items-end md:gap-8 md:p-10">
            <div className="md:col-span-7">
              <h3 className="font-display text-display-md md:text-display-lg font-bold tracking-tight text-white leading-tight">
                {card.title}
              </h3>
              <p className="mt-4 max-w-[32rem] text-body-lg text-white/85 leading-relaxed">
                {card.body}
              </p>
              <div className="mt-6">
                <a
                  href={card.action.href}
                  className="group inline-flex items-center gap-2.5 rounded-full bg-white px-5 py-2.5 text-caption font-bold text-ink hover:bg-surface transition-all shadow-md"
                >
                  <span>{card.action.label}</span>
                  <ArrowUpRightIcon className="size-3.5 transition-transform group-hover:rotate-45" />
                </a>
              </div>
            </div>

            {/* Chips & Highlights */}
            <ul className="flex flex-wrap gap-2 md:col-span-5 md:col-start-8 md:flex-col md:gap-2.5 lg:col-span-4 lg:col-start-9">
              {card.points.map((pt) => (
                <li
                  key={pt}
                  className="flex items-center gap-3 rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-body-sm font-semibold text-white backdrop-blur-md shadow-sm"
                >
                  <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-white" />
                  <span>{pt}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Receding dark veil */}
          <div
            data-veil=""
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-ink opacity-0 transition-opacity"
          />
        </article>
      </div>
    </div>
  );
}

export function StackedCards() {
  const { ref: headerRef } = useReveal<HTMLDivElement>();

  return (
    <section id="stakeholders" aria-labelledby="stakeholders-heading" className="relative bg-white pt-16">
      <div ref={headerRef} className="container-site">
        <SectionHeader
          headingId="stakeholders-heading"
          tag="WHO WE SERVE"
          heading="Three coordinated views of the same critical moment."
          body="Disasters require every participant—the citizen trapped on a roof, the crew piloting a boat, and the officer directing resources—to operate from a synchronized source of truth."
        />
      </div>

      <div className="relative">
        {stakeholderCards.map((card, index) => (
          <StackCard
            key={card.index}
            card={card}
            index={index}
            isLast={index === stakeholderCards.length - 1}
          />
        ))}
      </div>
    </section>
  );
}

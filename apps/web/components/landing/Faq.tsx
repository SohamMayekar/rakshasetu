"use client";

import { useState } from "react";
import { PlusIcon } from "@/components/landing/icons";
import { SectionTag } from "@/components/landing/SectionTag";
import { faqs } from "@/components/landing/content";
import { useReveal } from "@/hooks/use-reveal";
import { cn } from "@/lib/utils";

export function Faq() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const { ref: headerRef } = useReveal<HTMLDivElement>();
  const { ref: listRef } = useReveal<HTMLDivElement>();

  const toggle = (idx: number) => {
    setOpenIndex(openIndex === idx ? null : idx);
  };

  return (
    <section id="faq" aria-labelledby="faq-heading" className="section section-top bg-white">
      <div className="container-site grid gap-10 lg:grid-cols-12 lg:gap-16">
        {/* Left Side: Intro & Quick Help Box */}
        <div ref={headerRef} className="lg:col-span-5 flex flex-col justify-between">
          <div>
            <div data-reveal="">
              <SectionTag>FREQUENTLY ASKED QUESTIONS</SectionTag>
            </div>
            <h2
              id="faq-heading"
              data-reveal=""
              className="mt-5 font-display text-display-lg font-bold tracking-tight text-ink"
            >
              Questions answered plainly.
            </h2>
            <p data-reveal="" className="mt-4 text-body-lg text-slate leading-relaxed">
              Every design choice in RakshaSetu balances emergency speed, digital accessibility, and strict human accountability.
            </p>
          </div>

          {/* Help box */}
          <div data-reveal="" className="mt-10 rounded-2xl border border-hairline bg-surface p-6">
            <h3 className="font-display text-body font-bold text-ink">
              Need technical or deployment briefings?
            </h3>
            <p className="mt-2 text-caption text-slate leading-relaxed">
              For state disaster management authorities (SDMA), district magistrates, or SDRF/NDRF battallions evaluating RakshaSetu.
            </p>
            <div className="mt-4 flex gap-3">
              <a
                href="/login"
                className="inline-flex items-center rounded-full bg-ink px-4 py-2 text-caption font-bold text-white hover:bg-ink-soft transition-colors"
              >
                Access Control Room
              </a>
              <a
                href="/r"
                className="inline-flex items-center rounded-full border border-hairline bg-white px-4 py-2 text-caption font-bold text-ink hover:bg-surface transition-colors"
              >
                Try Citizen Portal
              </a>
            </div>
          </div>
        </div>

        {/* Right Side: Accordion Items */}
        <div ref={listRef} className="lg:col-span-7 space-y-3">
          {faqs.map((faq, index) => {
            const isOpen = openIndex === index;
            return (
              <div
                key={faq.question}
                data-reveal=""
                className={cn(
                  "lift rounded-2xl border transition-all duration-300",
                  isOpen
                    ? "border-black/20 bg-surface shadow-sm"
                    : "border-hairline bg-surface/60 hover:bg-surface hover:border-black/10",
                )}
              >
                <h3>
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => toggle(index)}
                    className="flex w-full items-center justify-between gap-4 p-5 md:p-6 text-left"
                  >
                    <span className="font-display text-lead font-bold tracking-tight text-ink">
                      {faq.question}
                    </span>
                    <span
                      className={cn(
                        "grid size-8 shrink-0 place-items-center rounded-full border border-hairline bg-white text-ink transition-transform duration-300",
                        isOpen && "rotate-45 bg-ink text-white",
                      )}
                    >
                      <PlusIcon className="size-4" />
                    </span>
                  </button>
                </h3>

                {/* Smooth Height Expansion with Grid Rows Trick */}
                <div
                  className={cn(
                    "grid transition-[grid-template-rows] duration-300 ease-site",
                    isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
                  )}
                >
                  <div className="overflow-hidden">
                    <p className="px-5 pb-6 md:px-6 md:pb-7 text-body text-slate leading-relaxed border-t border-hairline/80 pt-4">
                      {faq.answer}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

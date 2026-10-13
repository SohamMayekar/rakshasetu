"use client";

import { SectionHeader } from "@/components/landing/SectionHeader";
import { SlotImage } from "@/components/landing/SlotImage";
import { metrics, metricsIntro } from "@/components/landing/content";
import { useGsap } from "@/hooks/use-gsap";
import { useReveal } from "@/hooks/use-reveal";
import { EASE } from "@/lib/motion";
import { cn } from "@/lib/utils";

const COUNT_DURATION = 1.6;

export function useMetricCount<T extends HTMLElement>() {
  return useGsap<T>(({ el, q, gsap, ScrollTrigger }) => {
    q("[data-count]").forEach((node) => {
      node.textContent = `${node.getAttribute("data-prefix") ?? ""}0${node.getAttribute("data-suffix") ?? ""}`;
    });

    ScrollTrigger.create({
      trigger: el,
      start: "top 88%",
      once: true,
      onEnter: () => {
        q("[data-count]").forEach((node) => {
          const target = Number(node.getAttribute("data-count"));
          const prefix = node.getAttribute("data-prefix") ?? "";
          const suffix = node.getAttribute("data-suffix") ?? "";
          const proxy = { v: 0 };
          gsap.to(proxy, {
            v: target,
            duration: COUNT_DURATION,
            ease: EASE.power,
            onUpdate: () => {
              node.textContent = `${prefix}${Math.round(proxy.v)}${suffix}`;
            },
          });
        });
      },
    });
  });
}

export function Metrics() {
  const { ref: headerRef } = useReveal<HTMLDivElement>();
  const { ref: rowRef } = useReveal<HTMLDivElement>();
  const { ref: countRef } = useMetricCount<HTMLDivElement>();

  return (
    <section id="how-it-works" aria-labelledby="metrics-heading" className="section section-top bg-white">
      <div ref={headerRef} className="container-site">
        <SectionHeader
          headingId="metrics-heading"
          tag={metricsIntro.tag}
          heading={metricsIntro.heading}
          body={metricsIntro.body}
        />
      </div>

      <div
        ref={rowRef}
        className="container-site grid items-stretch gap-3.5 sm:grid-cols-2 lg:grid-cols-12 lg:gap-5"
      >
        {/* Left atmospheric situational awareness photo */}
        <figure
          data-reveal=""
          className="group relative w-full overflow-hidden rounded-2xl bg-surface aspect-[4/3] sm:aspect-[16/10] lg:col-span-3 lg:aspect-auto lg:min-h-[340px]"
        >
          <div data-reveal-image="" className="absolute inset-0">
            <SlotImage
              slot="metrics.left"
              sizes="(max-width: 1024px) 50vw, 340px"
              imageClassName="img-zoom"
            />
          </div>
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-t from-ink/70 via-transparent to-transparent"
          />
          <figcaption className="absolute bottom-4 left-4 right-4 text-[12px] font-semibold text-white/90">
            Multi-district command coordination center
          </figcaption>
        </figure>

        {/* Center 4 Metric Cards */}
        <div
          ref={countRef}
          className="grid gap-3.5 sm:col-span-2 sm:grid-cols-2 lg:col-span-6 lg:gap-5"
        >
          {metrics.map((m, idx) => (
            <article
              key={m.label}
              data-reveal=""
              className="lift flex flex-col justify-between rounded-2xl border border-hairline bg-surface p-6 sm:p-7 transition-colors hover:border-black/15"
            >
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold tracking-widest text-slate uppercase">
                  METRIC · 0{idx + 1}
                </span>
                <span className="size-2 rounded-full bg-slate/40" />
              </div>

              <div className="my-5">
                <p className="font-display text-numeral font-bold tracking-tight text-ink">
                  <span
                    data-count={m.value}
                    data-prefix=""
                    data-suffix={m.suffix}
                  >
                    {m.value}{m.suffix}
                  </span>
                </p>
                <h3 className="mt-2 font-display text-body font-bold text-ink">
                  {m.label}
                </h3>
              </div>

              <p className="text-body-sm text-slate border-t border-hairline pt-3.5">
                {m.detail}
              </p>
            </article>
          ))}
        </div>

        {/* Right atmospheric rescue boat photo */}
        <figure
          data-reveal=""
          className="group relative w-full overflow-hidden rounded-2xl bg-surface aspect-[4/3] sm:aspect-[16/10] lg:col-span-3 lg:aspect-auto lg:min-h-[340px]"
        >
          <div data-reveal-image="" className="absolute inset-0">
            <SlotImage
              slot="metrics.right"
              sizes="(max-width: 1024px) 50vw, 340px"
              imageClassName="img-zoom object-right"
            />
          </div>
          <div
            aria-hidden="true"
            className="absolute inset-0 bg-gradient-to-t from-ink/70 via-transparent to-transparent"
          />
          <figcaption className="absolute bottom-4 left-4 right-4 text-[12px] font-semibold text-white/90">
            SDRF / NDRF motorized boat dispatch
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

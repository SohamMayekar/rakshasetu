"use client";

import { Cta } from "@/components/landing/Cta";
import { SlotImage } from "@/components/landing/SlotImage";
import { marqueeItems } from "@/components/landing/content";
import { useGsap } from "@/hooks/use-gsap";

const START_WIDTH_RATIO = { mobile: 0.65, desktop: 0.42 } as const;
const START_HEIGHT_PX = 280;
const START_RADIUS_PX = 20;

function PhraseRun({ hidden = false }: { hidden?: boolean }) {
  return (
    <ul aria-hidden={hidden || undefined} className="flex w-max shrink-0 items-center">
      {marqueeItems.map((item) => (
        <li key={item} className="flex items-center">
          <span className="whitespace-nowrap px-8 font-display text-marquee font-bold tracking-tight text-ink md:px-12">
            {item}
          </span>
          <span aria-hidden="true" className="size-2.5 shrink-0 rounded-full bg-slate/40" />
        </li>
      ))}
    </ul>
  );
}

export function Marquee() {
  const { ref: runwayRef } = useGsap<HTMLDivElement>(({ el, q, isMobile, gsap }) => {
    const frame = q("[data-frame]")[0] as HTMLElement;
    const clip = q("[data-clip]")[0] as HTMLElement;
    const photo = q("[data-photo]")[0] as HTMLElement;
    const caption = q("[data-caption]")[0] as HTMLElement;

    if (!frame || !clip || !photo) return;

    const startClip = () => {
      const w = frame.offsetWidth;
      const h = frame.offsetHeight;
      const startRatio = isMobile ? START_WIDTH_RATIO.mobile : START_WIDTH_RATIO.desktop;
      const startW = Math.min(window.innerWidth * startRatio, w);
      const startH = Math.min(START_HEIGHT_PX, h);
      const x = Math.max((w - startW) / 2, 0);
      const y = Math.max((h - startH) / 2, 0);
      return `inset(${y}px ${x}px ${y}px ${x}px round ${START_RADIUS_PX}px)`;
    };

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: el,
        start: "top bottom",
        end: "bottom top",
        scrub: true,
        invalidateOnRefresh: true,
      },
    });

    tl.fromTo(
      clip,
      { clipPath: startClip() },
      { clipPath: "inset(0px 0px 0px 0px round 24px)", ease: "power2.out" },
      0,
    )
      .fromTo(photo, { scale: 1.25 }, { scale: 1, ease: "none" }, 0);

    if (caption) {
      tl.fromTo(caption, { opacity: 0, y: 20 }, { opacity: 1, y: 0, ease: "power2.out" }, 0.4);
    }
  });

  return (
    <section aria-label="Disaster Response Principles" className="relative overflow-hidden bg-white py-16 md:py-24">
      {/* Endless Band */}
      <div className="relative flex overflow-hidden py-6 select-none opacity-85">
        <div className="flex animate-marquee">
          <PhraseRun />
          <PhraseRun hidden />
        </div>
      </div>

      {/* Expanding Runway with centered expanding visual */}
      <div ref={runwayRef} className="container-site relative mt-6 min-h-[460px] md:min-h-[580px] flex items-center justify-center">
        <div
          data-frame=""
          className="relative w-full h-[460px] md:h-[580px]"
        >
          <div
            data-clip=""
            className="relative size-full overflow-hidden will-change-[clip-path]"
          >
            <div
              data-photo=""
              className="absolute inset-0 will-change-transform"
            >
              <SlotImage
                slot="marquee.photo"
                sizes="(max-width: 1320px) 100vw, 1320px"
                tone="dark"
                imageClassName="object-center"
              />
            </div>

            {/* Dark wash overlay */}
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-t from-ink/90 via-ink/40 to-ink/20"
            />

            {/* Caption & callout over expanded frame */}
            <div
              data-caption=""
              className="absolute inset-0 flex flex-col items-center justify-center p-6 text-center text-white"
            >
              <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-caption font-semibold backdrop-blur-md">
                Continuous District Accountability
              </span>
              <h3 className="mt-5 max-w-[20ch] font-display text-display-md font-bold tracking-tight text-white leading-tight">
                No life is lost to lost paperwork.
              </h3>
              <p className="mt-3 max-w-[28rem] text-body-lg text-white/80">
                A single universal desk uniting citizens, field rescue crews, and district magistrates.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Cta href="/login" tone="light" arrow magnetic shape="pill">
                  Open Control Room
                </Cta>
                <Cta href="/responder" tone="glass" shape="pill">
                  Explore Responder App
                </Cta>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

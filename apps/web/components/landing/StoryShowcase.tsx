"use client";

import { QuoteIcon, ArrowUpRightIcon } from "@/components/landing/icons";
import { SectionHeader } from "@/components/landing/SectionHeader";
import { SlotImage } from "@/components/landing/SlotImage";
import { fieldStories } from "@/components/landing/content";
import { useReveal } from "@/hooks/use-reveal";

export function StoryShowcase() {
  const { ref: headerRef } = useReveal<HTMLDivElement>();
  const { ref: featureRef } = useReveal<HTMLDivElement>();
  const { ref: gridRef } = useReveal<HTMLDivElement>();

  const [feature, ...rest] = fieldStories;

  return (
    <section id="field-stories" aria-labelledby="story-heading" className="section section-top bg-white font-body">
      <div ref={headerRef} className="container-site">
        <SectionHeader
          headingId="story-heading"
          tag="FIELD OPERATIONS"
          heading="First-hand accounts from high-stress rescue operations."
          body="Disasters test human courage and system reliability equally. Here is how field coordinators, volunteer boat crews, and rescued families experience RakshaSetu."
        />
      </div>

      <div className="container-site grid items-stretch gap-4 lg:grid-cols-12 lg:gap-6">
        {/* Left Column: Feature Story Card */}
        <div ref={featureRef} className="lg:col-span-5">
          <figure
            data-reveal=""
            className="group relative flex h-full min-h-[500px] flex-col justify-end overflow-hidden rounded-3xl bg-ink p-6 md:p-8 text-white shadow-xl"
          >
            <div data-reveal-image="" className="absolute inset-0">
              <SlotImage
                slot="story.feature"
                sizes="(max-width: 1024px) 100vw, 540px"
                tone="dark"
                imageClassName="img-zoom object-center"
              />
            </div>
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-gradient-to-t from-ink via-ink/65 to-transparent"
            />
            <div className="relative z-10 flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold tracking-widest text-[#cadccf] uppercase">
                  {feature.issue}
                </span>
                <QuoteIcon className="size-6 text-white/30" />
              </div>
              <blockquote className="font-accent text-display-sm font-normal italic leading-snug text-white">
                {feature.pullQuote}
              </blockquote>
              <p className="text-body-sm text-white/80">{feature.summary}</p>
              <figcaption className="flex items-center justify-between gap-3 border-t border-white/20 pt-4 mt-2">
                <div>
                  <span className="block font-display text-body font-bold text-white">
                    {feature.author}
                  </span>
                  <span className="text-caption text-white/60">{feature.role}</span>
                </div>
                <span className="grid size-8 place-items-center rounded-full bg-white text-ink">
                  <ArrowUpRightIcon className="size-4" />
                </span>
              </figcaption>
            </div>
          </figure>
        </div>

        {/* Right Column: Quieter Cards Grid */}
        <div ref={gridRef} className="grid gap-4 sm:grid-cols-2 lg:col-span-7">
          {rest.map((story) => (
            <figure
              key={story.author}
              data-reveal=""
              className="lift group relative flex h-full flex-col justify-between rounded-3xl border border-hairline bg-surface p-6 md:p-8 transition-colors hover:border-black/15"
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold tracking-widest text-slate uppercase">
                    {story.issue}
                  </span>
                  <QuoteIcon className="size-5 text-black/20" />
                </div>
                <blockquote className="mt-5 font-accent text-xl italic text-ink leading-relaxed">
                  {story.pullQuote}
                </blockquote>
                <p className="mt-3 text-body-sm text-slate">{story.summary}</p>
              </div>

              <figcaption className="mt-6 flex items-center justify-between gap-3 border-t border-hairline pt-4">
                <div>
                  <span className="block font-display text-body font-bold text-ink">
                    {story.author}
                  </span>
                  <span className="text-caption text-slate">{story.role}</span>
                </div>
                <span className="grid size-8 place-items-center rounded-full bg-white border border-hairline text-ink shadow-sm">
                  <ArrowUpRightIcon className="size-4" />
                </span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

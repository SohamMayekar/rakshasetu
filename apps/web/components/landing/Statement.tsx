"use client";

import { ArrowRightIcon } from "@/components/landing/icons";
import { SectionTag } from "@/components/landing/SectionTag";
import { statement } from "@/components/landing/content";
import { useGsap } from "@/hooks/use-gsap";
import { BLUR_TYPE } from "@/lib/motion";
import { cn } from "@/lib/utils";

type Token = { text: string; accent: boolean; trail?: string };

const SEGMENTS = [
  { text: statement.lead, accent: false },
  { text: statement.accent, accent: true },
  { text: statement.rest, accent: false },
  { text: statement.accentTwo, accent: true },
  { text: statement.tail, accent: false },
];

const SENTENCE = SEGMENTS.map((s) => s.text.trim()).join(" ").replace(/\s+([,.;:!?])/g, "$1");

function buildTokens(): Token[] {
  const tokens: Token[] = [];
  for (const segment of SEGMENTS) {
    for (const word of segment.text.split(/\s+/).filter(Boolean)) {
      const punct = /^[,.;:!?]+$/.test(word);
      const prev = tokens[tokens.length - 1];
      if (punct && prev) prev.trail = (prev.trail ?? "") + word;
      else tokens.push({ text: word, accent: segment.accent });
    }
  }
  return tokens;
}

const TOKENS = buildTokens();

function Chars({ text }: { text: string }) {
  return [...text].map((c, i) => (
    <span key={i} data-char="" className="inline-block">
      {c}
    </span>
  ));
}

export function Statement() {
  const { ref: textRef } = useGsap<HTMLParagraphElement>(({ el, gsap }) => {
    gsap.fromTo(
      el.querySelectorAll("[data-char]"),
      { filter: `blur(${BLUR_TYPE.blur}px)`, opacity: 0, willChange: "filter, opacity" },
      {
        ease: "none",
        filter: "blur(0px)",
        opacity: 1,
        stagger: BLUR_TYPE.stagger,
        scrollTrigger: { trigger: el, start: BLUR_TYPE.start, end: BLUR_TYPE.end, scrub: true },
      },
    );
  });

  return (
    <section
      id={statement.id}
      aria-label={statement.tag}
      className="relative bg-white py-24 md:py-36 overflow-hidden"
    >
      <div className="flex flex-col items-center">
        <SectionTag className="mb-8">{statement.tag}</SectionTag>
        <p
          ref={textRef}
          className="container-site mx-auto max-w-[1040px] text-balance text-center font-display text-display-md font-semibold tracking-[-0.035em] text-ink leading-[1.2]"
        >
          <span className="sr-only">{SENTENCE}</span>
          <span aria-hidden="true">
            {TOKENS.map((token, i) => (
              <span key={`${token.text}-${i}`}>
                {i > 0 ? " " : null}
                <span data-blur="" className="inline-block whitespace-nowrap">
                  <span className={cn(token.accent && "font-accent text-[1.14em] font-normal italic tracking-[-0.01em] text-[#2c3d44]")}>
                    <Chars text={token.text} />
                  </span>
                  {token.trail ? <Chars text={token.trail} /> : null}
                </span>
              </span>
            ))}
          </span>
        </p>

        <a
          href="#pillars"
          data-reveal=""
          className="group mt-12 inline-flex items-center gap-3 rounded-full border border-hairline bg-surface px-6 py-3 text-caption font-semibold text-ink transition-all hover:bg-black hover:text-white"
        >
          <span>See the six operational pillars</span>
          <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-1" />
        </a>
      </div>
    </section>
  );
}

import type { Gsap } from "@/lib/motion";

export const HERO_FRAME = {
  gap: { mobile: 12, desktop: 20 },
  radius: 24,
  travel: 360,
};

export function frameHero(gsap: Gsap, frame: Element, trigger: Element, isMobile: boolean) {
  const g = isMobile ? HERO_FRAME.gap.mobile : HERO_FRAME.gap.desktop;
  gsap.fromTo(
    frame,
    { clipPath: "inset(0px 0px 0px 0px round 0px)" },
    {
      clipPath: `inset(${g}px ${g}px 0px ${g}px round ${HERO_FRAME.radius}px)`,
      ease: "none",
      scrollTrigger: {
        trigger,
        start: "top top",
        end: `+=${HERO_FRAME.travel}`,
        scrub: 0.35,
        onRefresh: (self) => {
          self.animation?.progress(self.progress);
        },
      },
    },
  );
}

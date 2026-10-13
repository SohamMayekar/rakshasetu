/**
 * Motion vocabulary for RakshaSetu landing page.
 * Mirrors the House of Al Hadeetha cubic-bezier curves, GSAP CustomEase registration,
 * and lazy-loaded motion promise.
 */
import type { gsap as GsapNS } from "gsap";
import type { ScrollTrigger as ScrollTriggerNS } from "gsap/ScrollTrigger";

export type Gsap = typeof GsapNS;
export type ScrollTriggerStatic = typeof ScrollTriggerNS;
export type Motion = { gsap: Gsap; ScrollTrigger: ScrollTriggerStatic };

export const SITE_BEZIER = "0.22, 1, 0.36, 1";

let motionPromise: Promise<Motion> | null = null;

export function loadMotion(): Promise<Motion> {
  if (!motionPromise) {
    motionPromise = Promise.all([
      import("gsap"),
      import("gsap/ScrollTrigger"),
      import("gsap/CustomEase"),
    ]).then(([{ gsap }, { ScrollTrigger }, { CustomEase }]) => {
      gsap.registerPlugin(ScrollTrigger, CustomEase);
      try {
        CustomEase.create("site", `M0,0 C${SITE_BEZIER.replace(/\s/g, "")} 1,1`);
      } catch {
        // Fallback if already registered
      }
      gsap.defaults({ ease: "site", overwrite: "auto" });
      ScrollTrigger.config({ ignoreMobileResize: true });
      if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
        Object.assign(window, { gsap, ScrollTrigger });
      }
      return { gsap, ScrollTrigger };
    });
  }
  return motionPromise;
}

export const EASE = {
  glide: "cubic-bezier(0.25, 1.08, 0.35, 1)",
  out: "site",
  expo: "expo.out",
  power: "power3.out",
  inOut: "expo.inOut",
  elastic: "elastic.out(1, 0.45)",
} as const;

export const DUR = {
  micro: 0.3,
  exit: 0.4,
  base: 0.7,
  reveal: 0.9,
  slow: 1.2,
  image: 1.4,
} as const;

export const STAGGER = {
  tight: 0.04,
  base: 0.06,
  loose: 0.08,
} as const;

export const REVEAL = {
  scale: 0.9,
  y: 20,
  imageScale: 1.08,
  blur: 10,
} as const;

export const BLUR_TYPE = {
  blur: 10,
  stagger: 0.04,
  start: "top bottom",
  end: "center 42%",
} as const;

export const BP = {
  md: 768,
  lg: 1024,
} as const;

export const MEDIA = {
  desktop: `(min-width: ${BP.md}px)`,
  mobile: `(max-width: ${BP.md - 1}px)`,
  pointer: "(hover: hover) and (pointer: fine)",
} as const;

export function prefersReducedMotion() {
  if (typeof document === "undefined") return false;
  return document.documentElement.dataset.motion === "reduced";
}

export function hasFinePointer() {
  if (typeof window === "undefined") return false;
  return window.matchMedia(MEDIA.pointer).matches;
}

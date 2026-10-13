"use client";

import { useEffect, useRef, type DependencyList } from "react";

import {
  loadMotion,
  MEDIA,
  prefersReducedMotion,
  type Gsap,
  type ScrollTriggerStatic,
} from "@/lib/motion";

export type GsapSetupArgs<T extends HTMLElement> = {
  el: T;
  isDesktop: boolean;
  isMobile: boolean;
  q: ReturnType<Gsap["utils"]["selector"]>;
  gsap: Gsap;
  ScrollTrigger: ScrollTriggerStatic;
};

export function useGsap<T extends HTMLElement = HTMLDivElement>(
  setup: (args: GsapSetupArgs<T>) => void | (() => void),
  deps: DependencyList = [],
) {
  const ref = useRef<T>(null);
  const setupRef = useRef(setup);
  useEffect(() => {
    setupRef.current = setup;
  }, [setup]);

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;

    let cancelled = false;
    let revert: (() => void) | null = null;

    loadMotion().then(({ gsap, ScrollTrigger }) => {
      if (cancelled) return;
      const mm = gsap.matchMedia();
      mm.add({ isDesktop: MEDIA.desktop, isMobile: MEDIA.mobile }, (context) => {
        const conditions = context.conditions as { isDesktop: boolean; isMobile: boolean };
        const cleanup = setupRef.current({
          el,
          isDesktop: conditions.isDesktop,
          isMobile: conditions.isMobile,
          q: gsap.utils.selector(el),
          gsap,
          ScrollTrigger,
        });
        if (typeof cleanup === "function") return cleanup;
      });
      revert = () => mm.revert();
    });

    return () => {
      cancelled = true;
      revert?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ref };
}

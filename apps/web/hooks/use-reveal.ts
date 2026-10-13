"use client";

import { useEffect, useRef } from "react";

import { useGsap } from "@/hooks/use-gsap";
import { prefersReducedMotion } from "@/lib/motion";

type RevealOptions = {
  once?: boolean;
  start?: string;
  immediate?: boolean;
};

function indexTargets(el: HTMLElement) {
  const targets = el.matches("[data-reveal]")
    ? [el]
    : Array.from(el.querySelectorAll<HTMLElement>("[data-reveal]"));
  targets.forEach((t, i) => t.style.setProperty("--i", String(i)));
}

export function useReveal<T extends HTMLElement = HTMLDivElement>({
  once = false,
  start = "top 88%",
  immediate = false,
}: RevealOptions = {}) {
  const immediateRef = useRef<T>(null);

  useEffect(() => {
    const el = immediateRef.current;
    if (!immediate || !el || prefersReducedMotion()) return;
    indexTargets(el);
    const id = requestAnimationFrame(() => el.classList.add("is-in"));
    return () => cancelAnimationFrame(id);
  }, [immediate]);

  const { ref: scrollRef } = useGsap<T>(({ el, ScrollTrigger }) => {
    if (immediate) return;
    indexTargets(el);
    const enter = () => el.classList.add("is-in");
    const leave = () => {
      if (!once) el.classList.remove("is-in");
    };

    ScrollTrigger.create({
      trigger: el,
      start,
      onEnter: enter,
      onEnterBack: enter,
      onLeave: leave,
      onLeaveBack: leave,
    });
  });

  return { ref: immediate ? immediateRef : scrollRef };
}

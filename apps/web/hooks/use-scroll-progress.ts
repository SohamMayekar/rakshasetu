"use client";

import { useEffect, useRef } from "react";

import { useGsap } from "@/hooks/use-gsap";

type ProgressHandler = (progress: number, scrollY: number) => void;

type ProgressOptions = {
  start?: string;
  end?: string;
  desktopOnly?: boolean;
};

export function useScrollProgress<T extends HTMLElement = HTMLDivElement>(
  onProgress: ProgressHandler,
  { start = "top top", end = "bottom bottom", desktopOnly = false }: ProgressOptions = {},
) {
  const handler = useRef(onProgress);
  useEffect(() => {
    handler.current = onProgress;
  }, [onProgress]);

  return useGsap<T>(({ el, isMobile, ScrollTrigger }) => {
    if (desktopOnly && isMobile) return;
    ScrollTrigger.create({
      trigger: el,
      start,
      end,
      invalidateOnRefresh: true,
      onUpdate: (self) => handler.current(self.progress, self.scroll()),
      onRefresh: (self) => handler.current(self.progress, self.scroll()),
    });
  });
}

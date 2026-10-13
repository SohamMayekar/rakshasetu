"use client";

import type { ReactNode } from "react";

import { useGsap } from "@/hooks/use-gsap";
import { EASE, hasFinePointer, type Gsap } from "@/lib/motion";
import { cn } from "@/lib/utils";

type MagneticProps = {
  children: ReactNode;
  strength?: number;
  className?: string;
};

export function Magnetic({ children, strength = 0.28, className }: MagneticProps) {
  const { ref: wrapRef } = useGsap<HTMLSpanElement>(({ el, gsap }) => {
    if (!hasFinePointer()) return;
    const target = el.firstElementChild as HTMLElement | null;
    if (!target) return;

    let xTo: ReturnType<Gsap["quickTo"]> | null = null;
    let yTo: ReturnType<Gsap["quickTo"]> | null = null;

    const enter = () => {
      xTo = gsap.quickTo(target, "x", { duration: 0.45, ease: EASE.power });
      yTo = gsap.quickTo(target, "y", { duration: 0.45, ease: EASE.power });
    };
    const move = (e: PointerEvent) => {
      if (!xTo || !yTo) enter();
      const r = el.getBoundingClientRect();
      xTo?.((e.clientX - (r.left + r.width / 2)) * strength);
      yTo?.((e.clientY - (r.top + r.height / 2)) * strength);
    };
    const leave = () => {
      xTo = null;
      yTo = null;
      gsap.to(target, { x: 0, y: 0, duration: 0.85, ease: EASE.elastic });
    };

    el.addEventListener("pointerenter", enter);
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerleave", leave);
    return () => {
      el.removeEventListener("pointerenter", enter);
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerleave", leave);
    };
  });

  return (
    <span ref={wrapRef} className={cn("-m-3 inline-block p-3", className)}>
      <span className="inline-block will-change-transform">{children}</span>
    </span>
  );
}

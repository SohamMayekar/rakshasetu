"use client";

// The public landing page. It speaks to people asking for help and to the officers and teams who answer, equally.
// Visiting it never needs a session and never changes one. The sections live in their own files; this one only
// orders them and eases each block in as it arrives.

import { useEffect, useRef } from "react";

import type { Me } from "@/lib/api";

import { Faq, Final, Footer, Try } from "./Closing";
import { Hero } from "./Hero";
import { Nav } from "./Nav";
import { Audience, Brief, Ideas, Problem } from "./Sections";
import { Watch } from "./Watch";

export default function Landing({ me }: { me?: Me | null }) {
  const root = useRef<HTMLDivElement>(null);

  // Arm the scroll reveals once the page is live, then let each block ease in as it arrives.
  useEffect(() => {
    const el = root.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const items = Array.from(el.querySelectorAll<HTMLElement>(".rv"));
    el.setAttribute("data-rv", "");
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    items.forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, []);

  return (
    <div ref={root} className="lp min-h-dvh">
      <a href="#watch" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-paper">Skip to the story</a>
      <Nav me={me} />
      <main>
        <Hero />
        <Watch />
        <Problem />
        <Ideas />
        <Audience />
        <Brief />
        <Try me={me} />
        <Faq />
        <Final me={me} />
      </main>
      <Footer me={me} />
    </div>
  );
}

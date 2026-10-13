"use client";

import { ArrowRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import type { Me } from "@/lib/api";
import { signOut } from "@/lib/session";

import { DESK_ROLES, openDesk } from "./parts";

const LINKS: [string, string][] = [["#watch", "How it works"], ["#ideas", "Ideas"], ["#doors", "Who it is for"], ["#faq", "FAQ"]];

// One line, 64 px, floating. It goes solid once you scroll, and carries a thin reading-progress line.
export function Nav({ me }: { me?: Me | null }) {
  const [solid, setSolid] = useState(false);
  const bar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let f = 0;
    const on = () => {
      f = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setSolid(window.scrollY > 12);
      if (bar.current && max > 0) bar.current.style.transform = `scaleX(${Math.min(window.scrollY / max, 1)})`;
    };
    const h = () => { if (!f) f = requestAnimationFrame(on); };
    on();
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  // Whoever is signed in, as whatever kind of account, can open their own screen from here or sign out. Every
  // other part of this page works the same signed in or out.
  const mine = !me ? null : me.user.role === "team_lead" ? { href: "/responder", label: "Team app" }
    : DESK_ROLES.includes(me.user.role) ? { href: "/desk", label: "Open the desk" } : { href: "/?incidents", label: "Incidents" };

  return (
    <header className="fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-5">
      <nav aria-label="Main"
           className={`relative mx-auto flex h-16 max-w-6xl items-center overflow-hidden rounded-full border pl-4 pr-2 transition-[background-color,border-color,box-shadow,backdrop-filter] duration-300 ${solid ? "border-line bg-paper/85 shadow-[var(--shadow-card)] backdrop-blur-xl" : "border-transparent bg-transparent"}`}>
        <a href="#top" className="flex items-center gap-2.5 text-ink" aria-label="RakshaSetu, top of page">
          <Mark className="size-7" /><span className="text-[1.0625rem] font-semibold tracking-tight">RakshaSetu</span>
        </a>
        <ul className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-0.5 md:flex">
          {LINKS.map(([h, l]) => (
            <li key={h}><a href={h} className="rounded-full px-3.5 py-2 text-[0.9375rem] font-medium text-ink-2 transition-colors hover:bg-ink/[0.05] hover:text-ink">{l}</a></li>
          ))}
        </ul>
        <div className="ml-auto flex items-center gap-1.5">
          {mine && me ? (
            <>
              <button onClick={() => void signOut("/")} className="hidden h-10 items-center rounded-full px-3 text-[0.9375rem] font-medium text-ink-2 hover:text-ink sm:inline-flex">Sign out</button>
              <a href={mine.href} className="inline-flex h-11 items-center gap-1.5 rounded-full bg-ink px-5 text-[0.9375rem] font-semibold text-paper hover:bg-[#2b2b2b]">{mine.label}<ArrowRight className="size-4" aria-hidden /></a>
            </>
          ) : (
            <>
              <a href="/login" onClick={openDesk} className="hidden h-10 items-center rounded-full px-3 text-[0.9375rem] font-medium text-ink-2 hover:text-ink sm:inline-flex">Control room</a>
              <a href="/r" className="inline-flex h-11 items-center gap-1.5 rounded-full bg-ink px-5 text-[0.9375rem] font-semibold text-paper hover:bg-[#2b2b2b]">I need help<ArrowRight className="size-4" aria-hidden /></a>
            </>
          )}
        </div>
        <div aria-hidden className="absolute inset-x-6 bottom-0 h-[2px] overflow-hidden rounded-full">
          <div ref={bar} className="h-full origin-left scale-x-0 bg-[var(--lp-accent)]" />
        </div>
      </nav>
    </header>
  );
}

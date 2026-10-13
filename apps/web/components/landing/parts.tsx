"use client";

// Shared pieces of the landing page: the roles that get the desk, the one set of button, card and heading
// styles (so every section matches), and the drawn dawn scene that stands in until a hero photograph is added.

import type { LucideIcon } from "lucide-react";
import type { CSSProperties, ReactNode } from "react";

import type { Me } from "@/lib/api";
import { enterNationalDesk } from "@/lib/enter";

export const DESK_ROLES = ["call_taker", "duty_officer", "incharge", "admin"];

export const delay = (ms: number): CSSProperties => ({ ["--d" as string]: `${ms}ms` });

/** Where "the control room" leads: straight to the national desk for desk staff, otherwise to sign in. */
export const deskHref = (me?: Me | null) => (me && DESK_ROLES.includes(me.user.role) ? "/desk" : "/login");

/** One tap into the national desk (the demo listener signs the admin profile in; a signed-in person just goes). */
export const openDesk = (e: React.MouseEvent) => {
  e.preventDefault();
  void enterNationalDesk();
};

// One scale for the whole page: pills for anything you press, 28 px for a panel, 20 px for what sits inside one.
const pill = "inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-full px-6 text-[0.9375rem] font-semibold transition-[background-color,box-shadow,transform] duration-200 active:scale-[.98]";
export const btnPrimary = `${pill} bg-ink text-paper hover:bg-[#2b2b2b] hover:shadow-[var(--shadow-lift)]`;
export const btnSecondary = `${pill} border border-ink/15 bg-paper text-ink hover:border-ink/40 hover:shadow-[var(--shadow-card)]`;
export const panel = "rounded-[28px] border border-line/80 bg-paper shadow-[var(--shadow-card)]";
export const inner = "rounded-[20px]";

export function Em({ children }: { children: ReactNode }) {
  return <em className="lp-em">{children}</em>;
}

export function H2({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h2 className={`text-[1.9rem] font-semibold leading-[1.1] tracking-[-0.03em] sm:text-4xl lg:text-[2.6rem] ${className}`}>{children}</h2>;
}

/** The one icon treatment: the accent on its soft wash. */
export function IconWell({ icon: Icon, size = "md", inverted = false }: { icon: LucideIcon; size?: "sm" | "md" | "lg"; inverted?: boolean }) {
  const box = { sm: "size-9 rounded-xl", md: "size-11 rounded-2xl", lg: "size-14 rounded-[18px]" }[size];
  const glyph = { sm: "size-4", md: "size-5", lg: "size-6" }[size];
  return (
    <span className={`grid shrink-0 place-items-center ${box} ${inverted ? "bg-paper/12 text-paper" : "bg-[var(--lp-wash)] text-[var(--lp-accent)]"}`}>
      <Icon className={glyph} strokeWidth={1.9} aria-hidden />
    </span>
  );
}

/**
 * First light over hills, a bridge and a small town: the page's backdrop for the hero and the closing block. It is
 * deliberately about no one disaster. A photograph (public/images/hero.webp, see docs/HERO_IMAGE.md) replaces it.
 */
export function Landscape({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 1440 360" preserveAspectRatio="xMidYMax slice" className={className} aria-hidden>
      <defs>
        <linearGradient id="ls-m1" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#b9cde0" /><stop offset="1" stopColor="#dbe6ef" /></linearGradient>
        <linearGradient id="ls-m2" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#9db8cf" /><stop offset="1" stopColor="#cfdce8" /></linearGradient>
        <linearGradient id="ls-m3" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#7f9db8" /><stop offset="1" stopColor="#c3d3e1" /></linearGradient>
        <linearGradient id="ls-w" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#cfe0ee" /><stop offset="1" stopColor="#eef3f7" /></linearGradient>
      </defs>
      <path d="M0 210 L120 150 L230 200 L360 120 L500 205 L640 140 L780 215 L930 130 L1090 210 L1230 150 L1340 195 L1440 160 V360 H0Z" fill="url(#ls-m1)" />
      <path d="M0 250 L150 190 L290 240 L440 170 L600 250 L760 185 L920 255 L1080 180 L1230 245 L1440 200 V360 H0Z" fill="url(#ls-m2)" />
      <path d="M0 290 L170 235 L330 285 L520 225 L700 290 L880 230 L1060 292 L1240 235 L1440 280 V360 H0Z" fill="url(#ls-m3)" opacity=".85" />
      {/* a small town on the near hills */}
      <g fill="#6f879c" opacity=".7">
        <rect x="1010" y="268" width="26" height="30" /><rect x="1040" y="260" width="22" height="38" /><rect x="1066" y="272" width="30" height="26" />
        <rect x="1100" y="264" width="20" height="34" /><rect x="1124" y="274" width="28" height="24" />
        <rect x="250" y="280" width="24" height="26" /><rect x="278" y="272" width="20" height="34" /><rect x="302" y="282" width="28" height="24" />
      </g>
      <rect x="0" y="300" width="1440" height="60" fill="url(#ls-w)" />
      <g fill="none" stroke="#5b7389" strokeWidth="5" strokeLinecap="round" opacity=".75">
        <path d="M470 306 H970" /><path d="M520 306 a200 112 0 0 1 400 0" />
        <path d="M570 306 v-26 M620 306 v-52 M670 306 v-72 M720 306 v-80 M770 306 v-72 M820 306 v-52 M870 306 v-26" strokeWidth="2.5" />
      </g>
    </svg>
  );
}

export function Tag({ children }: { children: ReactNode }) {
  return <span className="inline-block rounded-full border border-line bg-paper/80 px-3 py-1 text-micro font-semibold uppercase tracking-[0.14em] text-ink-2">{children}</span>;
}

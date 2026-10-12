"use client";

// The app's left rail (every desk-side screen): where you can go, who you are, and, in a demo, that every
// person and phone on screen is synthetic. On the desk it folds to icons so the map keeps its width.
// Calm: neutral only (hue means priority), the current page is a quiet wash, never a colour.

import { Activity, ClipboardList, Handshake, LayoutGrid, LogOut, type LucideIcon, Presentation, ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";

import type { Me } from "@/lib/api";

export function Mark({ className = "size-8" }: { className?: string }) {
  // A bridge's arch inside a shield: "RakshaSetu", the bridge of protection. Ink only.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <path d="M16 2.5 4.5 7v8.2c0 7.1 4.9 12.3 11.5 14.3 6.6-2 11.5-7.2 11.5-14.3V7L16 2.5Z" fill="currentColor" />
      <path d="M9 20.5v-2.2a7 7 0 0 1 14 0v2.2" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M8 21h16" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

type Item = { href: string; label: string; icon: LucideIcon; show: boolean; match?: (p: string) => boolean };

function initials(name: string) {
  return name.replace(/[^A-Za-z ]/g, " ").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
}

function navItems(me: Me | null): Item[] {
  const can = (p: string) => !!me?.permissions.includes(p);
  const desk = !!me && ["call_taker", "duty_officer", "incharge", "admin"].includes(me.user.role);
  const all: Item[] = [
    { href: "/", label: "Incidents", icon: LayoutGrid, show: true, match: (p: string) => p === "/" },
    ...(me?.incidents ?? []).filter(() => desk).map((i) => ({
      href: `/desk/${i.code}`, label: `Desk · ${i.code}`, icon: ClipboardList, show: true, match: (p: string) => p.startsWith(`/desk/${i.code}`) })),
    { href: "/surge", label: "Surge", icon: Activity, show: can("totals.view") },
    { href: "/audit", label: "Audit", icon: ShieldCheck, show: can("audit.read") },
    { href: "/partners", label: "Partner log", icon: Handshake, show: can("audit.read") },
    { href: "/demo", label: "Demo controls", icon: Presentation, show: !!me?.demo_mode && can("incident.admin") },
  ];
  return all.filter((i) => i.show);
}

const isOn = (i: Item, path: string) => (i.match ? i.match(path) : path.startsWith(i.href));

// Below the desk breakpoint the sidebar folds into one row across the top of the page.
export function PhoneBar({ me }: { me: Me | null }) {
  const path = usePathname() ?? "/";
  return (
    <nav className="flex items-center gap-1 overflow-x-auto px-3 pt-3 md:hidden" aria-label="Navigation">
      <a href="/" className="mr-1 shrink-0 text-ink" title="RakshaSetu"><Mark className="size-7" /></a>
      {navItems(me).map((i) => {
        const Icon = i.icon;
        return (
          <a key={i.href} href={i.href} aria-current={isOn(i, path) ? "page" : undefined}
             className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-[13px] ${isOn(i, path) ? "bg-paper font-medium text-ink shadow-[var(--shadow-card)]" : "text-ink-2"}`}>
            <Icon className="size-4" strokeWidth={1.8} aria-hidden />{i.label}
          </a>
        );
      })}
    </nav>
  );
}

export function Sidebar({ me, compact = false }: { me: Me | null; compact?: boolean }) {
  const path = usePathname() ?? "/";
  const items = navItems(me);
  const on = (i: Item) => isOn(i, path);

  return (
    <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col py-5 md:flex ${compact ? "w-[68px] items-center px-2" : "w-60 px-4"}`}
           aria-label="Navigation">
      <a href="/" className={`flex items-center gap-2.5 text-ink ${compact ? "" : "px-2"}`} title="RakshaSetu">
        <Mark className="size-8 shrink-0" />
        {!compact && <span className="text-[17px] font-semibold tracking-tight">RakshaSetu</span>}
      </a>

      <nav className={`mt-8 flex flex-col gap-1 ${compact ? "items-center" : ""}`}>
        {items.map((i) => {
          const Icon = i.icon;
          return (
            <a key={i.href} href={i.href} title={compact ? i.label : undefined} aria-current={on(i) ? "page" : undefined}
               className={`flex items-center gap-3 rounded-xl text-sm transition-colors ${compact ? "size-11 justify-center" : "h-10 px-3"}
                 ${on(i) ? "bg-paper font-medium text-ink shadow-[0_1px_2px_rgba(20,20,20,0.06)]" : "text-ink-2 hover:bg-black/[0.04] hover:text-ink"}`}>
              <Icon className="size-[18px] shrink-0" strokeWidth={1.8} aria-hidden />
              {!compact && <span className="truncate">{i.label}</span>}
              {compact && <span className="sr-only">{i.label}</span>}
            </a>
          );
        })}
      </nav>

      <div className="flex-1" />

      {!compact && me?.demo_mode && (
        <div className="mb-4 rounded-2xl bg-paper p-4 text-xs leading-relaxed text-ink-2 shadow-[0_1px_2px_rgba(20,20,20,0.05)]">
          <p className="text-sm font-semibold text-ink">Demo mode</p>
          <p className="mt-1">Every person and phone number here is made up. The demo clock runs 60× faster.</p>
        </div>
      )}

      {me && (
        <div className={`flex items-center gap-2.5 ${compact ? "flex-col" : "px-1"}`}>
          <span className="grid size-9 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-paper" title={`${me.user.name} · ${me.user.role_label}`}>
            {initials(me.user.name)}
          </span>
          {!compact && (
            <span className="min-w-0 flex-1 leading-tight">
              <span className="block truncate text-sm font-medium">{me.user.name}</span>
              <span className="block truncate text-xs text-ink-3">{me.user.role_label}</span>
            </span>
          )}
          <a href="/login" onClick={() => fetch("/v1/auth/logout", { method: "POST" })} title="Sign out"
             className="grid size-9 shrink-0 place-items-center rounded-full text-ink-3 hover:bg-black/[0.05] hover:text-ink">
            <LogOut className="size-4" strokeWidth={1.8} aria-hidden /><span className="sr-only">Sign out</span>
          </a>
        </div>
      )}
    </aside>
  );
}

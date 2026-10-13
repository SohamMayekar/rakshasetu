"use client";

// The app's left rail (every desk-side screen): where you can go, who you are, and, in a demo, that every
// person and phone on screen is synthetic. On the desk it folds to icons so the map keeps its width.
// Calm: neutral only (hue means priority), the current page is a quiet wash, never a colour.

import { BellRing, ClipboardList, FileSpreadsheet, Gauge, Globe, LayoutDashboard, LifeBuoy, ListChecks, LogOut, type LucideIcon, ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type { Me } from "@/lib/api";
import { signOut } from "@/lib/session";

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

type Item = {
  href: string; label: string; icon: LucideIcon; show: boolean; group: "top" | "ops" | "intake" | "admin";
  match?: (p: string) => boolean; badge?: "alerts" | "sensors";
};

function initials(name: string) {
  return name.replace(/[^A-Za-z ]/g, " ").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
}

const GROUPS: { key: Item["group"]; title: string | null }[] = [
  { key: "top", title: null }, { key: "ops", title: "Operations" }, { key: "intake", title: "Intake and signals" }, { key: "admin", title: "Admin" },
];

// The desk's places: the one national desk, every case, the teams, the alerts and the volunteer sheets (all of them
// across every incident this person may see), the sensors, then the admin's own: incidents and History.
function navItems(me: Me | null): Item[] {
  const can = (p: string) => !!me?.permissions.includes(p);
  const desk = !!me && ["call_taker", "duty_officer", "incharge", "admin"].includes(me.user.role);
  const base = "/desk";
  const all: Item[] = [
    { href: "/", label: "Home page", icon: LayoutDashboard, show: true, group: "top", match: () => false },
    { href: base, label: "Desk", icon: ClipboardList, show: desk, group: "ops", match: (p) => p === base },
    { href: `${base}/cases`, label: "Cases", icon: ListChecks, show: desk && can("queue.view"), group: "ops" },
    { href: `${base}/teams`, label: "Teams", icon: LifeBuoy, show: desk && can("queue.view"), group: "ops" },
    { href: `${base}/alerts`, label: "Alerts", icon: BellRing, show: desk && can("escalation.ack"), group: "ops", badge: "alerts" },
    { href: `${base}/sheets`, label: "Sheets", icon: FileSpreadsheet, show: desk && can("import.run"), group: "intake" },
    { href: `${base}/sensors`, label: "Sensors", icon: Gauge, show: desk && can("totals.view"), group: "intake", badge: "sensors" },
    { href: `${base}/incidents`, label: "Incidents", icon: Globe, show: desk && can("incident.admin"), group: "admin" },
    { href: "/audit", label: "History", icon: ShieldCheck, show: can("audit.read"), group: "admin" },
  ];
  return all.filter((i) => i.show);
}

const isOn = (i: Item, path: string) => (i.match ? i.match(path) : path === i.href || path.startsWith(`${i.href}/`));

// The two numbers worth a glance from anywhere: teams not heard from, and sensors in danger. Quiet if the
// person may not see them or the call fails; refreshed every 15 s.
function useBadges(me: Me | null): Record<"alerts" | "sensors", number> {
  const [n, setN] = useState({ alerts: 0, sensors: 0 });
  const canAlerts = !!me?.permissions.includes("escalation.ack");
  const canSensors = !!me?.permissions.includes("totals.view") && !!me && ["call_taker", "duty_officer", "incharge", "admin"].includes(me.user.role);
  useEffect(() => {
    if (!canAlerts && !canSensors) return;
    let alive = true;
    const load = async () => {
      const next = { alerts: 0, sensors: 0 };
      try {
        if (canAlerts) {
          const r = await fetch("/v1/escalations?open=true", { cache: "no-store" });
          if (r.ok) next.alerts = ((await r.json()) as { status: string }[]).filter((e) => e.status !== "resolved").length;
        }
        if (canSensors) {
          const r = await fetch("/v1/telemetry", { cache: "no-store" });
          if (r.ok) next.sensors = ((await r.json()) as { state: string }[]).filter((s) => s.state === "danger").length;
        }
      } catch { /* quiet: a badge is a convenience */ }
      if (alive) setN(next);
    };
    void load();
    const t = setInterval(load, 15_000);
    return () => { alive = false; clearInterval(t); };
  }, [canAlerts, canSensors]);
  return n;
}

function onSignOut(e: React.MouseEvent) {
  e.preventDefault();   // let the sign-out finish before leaving, or the cookie can outlive the click
  void signOut("/");
}

function Badge({ n, tone = "ink" }: { n: number; tone?: "ink" | "light" }) {
  if (n <= 0) return null;
  return (
    <span aria-label={`${n} need attention`}
          className={`tabular grid h-5 min-w-5 place-items-center rounded-full px-1.5 text-micro font-semibold ${tone === "ink" ? "bg-ink text-paper" : "bg-paper text-ink"}`}>
      {n > 99 ? "99+" : n}
    </span>
  );
}

// Below the desk breakpoint the sidebar folds into one row across the top of the page.
export function PhoneBar({ me }: { me: Me | null }) {
  const path = usePathname() ?? "/";
  const items = navItems(me);
  const badges = useBadges(me);
  const row = useRef<HTMLElement>(null);
  useEffect(() => {   // keep the current page in view as the row scrolls sideways
    row.current?.querySelector("[aria-current='page']")?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [path, items.length]);
  return (
    <nav ref={row} className="scroll-quiet flex items-center gap-1 overflow-x-auto px-3 pt-3 md:hidden" aria-label="Navigation">
      <a href="/" className="mr-1 shrink-0 text-ink" title="RakshaSetu"><Mark className="size-7" /></a>
      {items.map((i) => {
        const Icon = i.icon;
        const on = isOn(i, path);
        return (
          <a key={i.href} href={i.href} aria-current={on ? "page" : undefined}
             className={`flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3 text-small transition-[background-color,color,box-shadow] duration-200 ${on ? "bg-paper font-medium text-ink shadow-[var(--shadow-card)]" : "text-ink-2 active:bg-black/[0.05]"}`}>
            <Icon className="size-4" strokeWidth={1.8} aria-hidden />{i.label}
            {i.badge && <Badge n={badges[i.badge]} />}
          </a>
        );
      })}
    </nav>
  );
}

export function Sidebar({ me, compact = false }: { me: Me | null; compact?: boolean }) {
  const path = usePathname() ?? "/";
  const items = navItems(me);
  const badges = useBadges(me);
  const [hover, setHover] = useState(false);
  const wide = !compact || hover;            // labels showing: always on full pages, on hover or focus on the desk
  const list = useRef<HTMLDivElement>(null);
  const [mark, setMark] = useState<{ top: number; height: number } | null>(null);

  // One quiet marker that glides to the current page instead of every item flashing its own background.
  useLayoutEffect(() => {
    const el = list.current?.querySelector<HTMLElement>("[aria-current='page']");
    setMark(el ? { top: el.offsetTop, height: el.offsetHeight } : null);
  }, [path, items.length, wide]);

  return (
    <aside aria-label="Navigation" className={`sticky top-0 z-30 hidden h-dvh shrink-0 md:block ${compact ? "w-[68px]" : "w-60"}`}>
      <div onMouseEnter={() => compact && setHover(true)} onMouseLeave={() => setHover(false)}
           onFocus={() => compact && setHover(true)} onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setHover(false); }}
           className={`absolute inset-y-0 left-0 flex flex-col overflow-hidden py-5 transition-[width,box-shadow,background-color] duration-300 ease-[cubic-bezier(.22,1,.36,1)]
             ${compact ? (wide ? "w-[236px] rounded-r-3xl bg-canvas px-3 shadow-[var(--shadow-lift)]" : "w-[68px] bg-transparent px-3") : "w-60 px-3"}`}>
        <a href="/" className="flex h-10 shrink-0 items-center gap-2.5 px-1.5 text-ink" title="RakshaSetu">
          <Mark className="size-8 shrink-0" />
          <span className={`overflow-hidden whitespace-nowrap text-heading font-semibold tracking-tight transition-[opacity,max-width] duration-300 ${wide ? "max-w-40 opacity-100" : "max-w-0 opacity-0"}`}>RakshaSetu</span>
        </a>

        <nav className="scroll-quiet mt-6 min-h-0 flex-1 overflow-y-auto overflow-x-hidden">
          <div ref={list} className="relative">
            {mark && (
              <span aria-hidden className="pointer-events-none absolute inset-x-0 rounded-xl bg-paper shadow-[0_1px_2px_rgba(20,20,20,0.06),0_4px_14px_rgba(20,20,20,0.05)] transition-[transform,height] duration-300 ease-[cubic-bezier(.22,1,.36,1)]"
                    style={{ height: mark.height, transform: `translateY(${mark.top}px)` }} />
            )}
            {GROUPS.map((g) => {
              const group = items.filter((i) => i.group === g.key);
              if (!group.length) return null;
              return (
                <div key={g.key} className={g.key === "top" ? "" : "mt-5"}>
                  {/* a fixed-height row, so nothing below it moves while the rail opens */}
                  {g.title && (
                    <div className="relative mb-1 flex h-5 items-center px-3">
                      <p aria-hidden={!wide} className={`whitespace-nowrap text-micro font-semibold uppercase tracking-[0.12em] text-ink-3 transition-opacity duration-300 ${wide ? "opacity-100" : "opacity-0"}`}>{g.title}</p>
                      <span aria-hidden className={`absolute inset-x-3 h-px bg-line transition-opacity duration-300 ${wide ? "opacity-0" : "opacity-100"}`} />
                    </div>
                  )}
                  <ul className="flex flex-col gap-0.5">
                    {group.map((i) => {
                      const Icon = i.icon;
                      const on = isOn(i, path);
                      const n = i.badge ? badges[i.badge] : 0;
                      return (
                        <li key={i.href}>
                          <a href={i.href} title={wide ? undefined : i.label} aria-current={on ? "page" : undefined}
                             className={`group relative flex h-11 items-center gap-3 rounded-xl px-3 text-body transition-colors duration-200
                               ${on ? "font-medium text-ink" : "text-ink-2 hover:bg-black/[0.04] hover:text-ink"}`}>
                            <span className="relative grid size-5 shrink-0 place-items-center">
                              <Icon className={`size-[18px] transition-transform duration-200 ${on ? "" : "group-hover:scale-110"}`} strokeWidth={on ? 2.1 : 1.8} aria-hidden />
                              {n > 0 && !wide && <span aria-hidden className="absolute -right-1 -top-1 size-2 rounded-full bg-ink ring-2 ring-canvas" />}
                            </span>
                            <span className={`min-w-0 flex-1 truncate transition-opacity duration-200 ${wide ? "opacity-100" : "opacity-0"}`}>{i.label}</span>
                            {wide && <Badge n={n} />}
                          </a>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
          </div>
        </nav>

        {wide && me?.demo_mode && (   // honesty (CLAUDE.md §1.6): one line, not a banner
          <p className="mb-3 mt-3 px-2 text-small leading-snug text-ink-3">Demo data: made-up people and phone numbers. The clock runs 60× faster.</p>
        )}

        {me && (
          <div className="mt-2 flex shrink-0 items-center gap-2.5 px-1 py-1.5">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-ink text-small font-semibold text-paper" title={`${me.user.name} · ${me.user.role_label}`}>
              {initials(me.user.name)}
            </span>
            <span className={`min-w-0 flex-1 overflow-hidden leading-tight transition-opacity duration-200 ${wide ? "opacity-100" : "pointer-events-none opacity-0"}`}>
              <span className="block truncate text-body font-medium">{me.user.name}</span>
              {me.user.role_label !== me.user.name && <span className="block truncate text-small text-ink-3">{me.user.role_label}</span>}
            </span>
            <a href="/" onClick={onSignOut} title="Sign out" tabIndex={wide ? 0 : -1}
               className={`grid size-9 shrink-0 place-items-center rounded-full text-ink-3 transition-[opacity,background-color,color] hover:bg-black/[0.05] hover:text-ink ${wide ? "opacity-100" : "pointer-events-none opacity-0"}`}>
              <LogOut className="size-4" strokeWidth={1.8} aria-hidden /><span className="sr-only">Sign out</span>
            </a>
          </div>
        )}
      </div>
    </aside>
  );
}

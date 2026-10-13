"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ArrowUpRightIcon, ArrowRightIcon } from "@/components/landing/icons";
import { Mark } from "@/components/shell/Sidebar";
import { navLinks } from "@/components/landing/content";
import type { Me } from "@/lib/api";
import { cn } from "@/lib/utils";

const FLOAT_AFTER = 36;

export function SiteNav({ me }: { me?: Me | null }) {

  const [floating, setFloating] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeHash, setActiveHash] = useState("#top");
  const [hoveredHash, setHoveredHash] = useState<string | null>(null);

  const fillRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const pillRef = useRef<HTMLSpanElement>(null);

  // Scroll tracking for floating state and top progress bar
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const y = window.scrollY;
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      setFloating(y > FLOAT_AFTER);
      if (fillRef.current && maxScroll > 0) {
        fillRef.current.style.transform = `scaleX(${Math.min(y / maxScroll, 1)})`;
      }

      // Update active hash based on visible section
      const sections = navLinks.map((l) => l.href.replace("#", ""));
      for (let i = sections.length - 1; i >= 0; i--) {
        const sec = document.getElementById(sections[i]);
        if (sec) {
          const rect = sec.getBoundingClientRect();
          if (rect.top <= window.innerHeight * 0.4) {
            setActiveHash(`#${sections[i]}`);
            break;
          }
        }
      }
    };

    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Update animated indicator pill position inside the glass capsule
  const indicated = hoveredHash ?? activeHash;

  useEffect(() => {
    if (!listRef.current || !pillRef.current) return;
    const activeEl = listRef.current.querySelector<HTMLElement>(`[data-hash="${indicated}"]`);
    if (activeEl) {
      const { offsetLeft, offsetWidth } = activeEl;
      pillRef.current.style.transform = `translateX(${offsetLeft}px)`;
      pillRef.current.style.width = `${offsetWidth}px`;
      pillRef.current.style.opacity = "1";
    } else {
      pillRef.current.style.opacity = "0";
    }
  }, [indicated]);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (menuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  return (
    <>
      {/* Top scroll-reading progress bar */}
      <div
        ref={fillRef}
        aria-hidden="true"
        className="fixed inset-x-0 top-0 z-[100] h-[2.5px] origin-left bg-gradient-to-r from-white via-[#cadccf] to-white/90 will-change-transform"
        style={{ transform: "scaleX(0)" }}
      />

      {/* Main navigation header */}
      <header
        ref={navRef}
        className={cn(
          "fixed inset-x-0 top-0 z-50 flex items-center justify-center transition-all duration-500 ease-site",
          floating ? "py-3.5 px-4" : "py-5 px-6 md:px-10",
        )}
      >
        <nav
          aria-label="Main Navigation"
          className={cn(
            "relative flex w-full max-w-[1320px] items-center justify-between transition-all duration-500 ease-site",
            floating
              ? "rounded-full border border-black/10 bg-white/80 px-4 py-2 text-ink shadow-[0_16px_40px_-12px_rgba(8,11,15,0.18)] backdrop-blur-xl dark:border-white/15 dark:bg-ink/80 dark:text-white"
              : "rounded-2xl border border-white/20 bg-white/10 px-5 py-3 text-white backdrop-blur-md",
          )}
        >
          {/* Brand Mark */}
          <a
            href="#top"
            className="group flex items-center gap-2.5 font-display text-body font-bold tracking-tight text-current"
          >
            <span className={cn(
              "grid size-9 place-items-center rounded-xl transition-all duration-300",
              floating ? "bg-ink text-white" : "bg-white text-ink",
            )}>
              <Mark className="size-5" />
            </span>
            <div className="flex flex-col text-left">
              <span className="text-body font-bold tracking-tight">RakshaSetu</span>
              <span className={cn(
                "text-[10px] font-medium tracking-wide uppercase",
                floating ? "text-slate-light" : "text-white/70",
              )}>
                National Layer
              </span>
            </div>
          </a>

          {/* Desktop Nav Capsule with sliding pill */}
          <div className="hidden lg:flex items-center">
            <ul
              ref={listRef}
              className={cn(
                "relative flex items-center gap-1 rounded-full p-1 text-caption font-semibold transition-colors duration-300",
                floating
                  ? "border border-black/5 bg-black/5 text-ink/75"
                  : "border border-white/15 bg-white/10 text-white/85",
              )}
            >
              <span
                ref={pillRef}
                aria-hidden="true"
                className={cn(
                  "pointer-events-none absolute inset-y-1 rounded-full transition-[transform,width,opacity] duration-300 ease-site",
                  floating ? "bg-white shadow-sm" : "bg-white/20 backdrop-blur-md",
                )}
                style={{ opacity: 0 }}
              />
              {navLinks.map((link) => {
                const isSelected = activeHash === link.href;
                return (
                  <li key={link.href} data-hash={link.href} className="relative z-10">
                    <a
                      href={link.href}
                      onMouseEnter={() => setHoveredHash(link.href)}
                      onMouseLeave={() => setHoveredHash(null)}
                      className={cn(
                        "inline-block rounded-full px-3.5 py-1.5 transition-colors duration-200",
                        isSelected
                          ? floating ? "text-ink font-bold" : "text-white font-bold"
                          : floating ? "hover:text-ink" : "hover:text-white",
                      )}
                    >
                      {link.label}
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Action CTAs */}
          <div className="flex items-center gap-2.5">
            {me ? (
              <>
                <Link
                  href={me.user.role === "team_lead" ? "/responder" : (me.incidents[0] ? `/desk/${me.incidents[0].code}` : "/login")}
                  className={cn(
                    "hidden sm:inline-flex items-center gap-2 rounded-full border px-4 py-2 text-caption font-bold transition-all shadow-sm",
                    floating
                      ? "border-black/15 bg-black/5 text-ink hover:bg-black/10"
                      : "border-white/30 bg-white/15 text-white hover:bg-white/25",
                  )}
                >
                  <span className="size-2 rounded-full bg-[#15803d]" />
                  <span>{me.team?.name ? `${me.team.name}` : me.user.name}</span>
                  <ArrowRightIcon className="size-3" />
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    fetch("/v1/auth/logout", { method: "POST" }).then(() => {
                      location.href = "/";
                    });
                  }}
                  className={cn(
                    "text-caption font-medium px-2 py-1 underline transition-colors",
                    floating ? "text-slate hover:text-ink" : "text-white/70 hover:text-white",
                  )}
                >
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link
                  href="/login"
                  className={cn(
                    "hidden sm:inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-caption font-semibold transition-colors",
                    floating
                      ? "text-ink/80 hover:text-ink hover:bg-black/5"
                      : "text-white/90 hover:text-white hover:bg-white/10",
                  )}
                >
                  Control Room
                </Link>

                <Link
                  href="/responder"
                  className={cn(
                    "hidden md:inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-caption font-semibold transition-colors",
                    floating
                      ? "border-black/15 text-ink hover:bg-black/5"
                      : "border-white/25 text-white hover:bg-white/15",
                  )}
                >
                  Responder App
                </Link>
              </>
            )}

            <Link
              href="/r"
              className={cn(
                "group press flex h-9 md:h-10 items-center gap-2 rounded-full px-4 text-caption font-bold transition-all shadow-sm",
                floating
                  ? "bg-ink text-white hover:bg-ink-soft"
                  : "bg-white text-ink hover:bg-surface",
              )}
            >
              <span>Ask for help</span>
              <span className={cn(
                "grid size-5 place-items-center rounded-full transition-transform duration-300 group-hover:rotate-45",
                floating ? "bg-white text-ink" : "bg-ink text-white",
              )}>
                <ArrowUpRightIcon className="size-3" />
              </span>
            </Link>

            {/* Mobile hamburger button */}
            <button
              type="button"
              aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(!menuOpen)}
              className={cn(
                "grid size-9 md:size-10 place-items-center rounded-full lg:hidden transition-colors",
                floating ? "bg-black/5 text-ink" : "bg-white/15 text-white",
              )}
            >
              <div className="flex flex-col gap-1.5 w-4">
                <span
                  className={cn(
                    "block h-0.5 w-full bg-current transition-transform duration-300",
                    menuOpen && "translate-y-2 rotate-45",
                  )}
                />
                <span
                  className={cn(
                    "block h-0.5 w-full bg-current transition-opacity duration-300",
                    menuOpen && "opacity-0",
                  )}
                />
                <span
                  className={cn(
                    "block h-0.5 w-full bg-current transition-transform duration-300",
                    menuOpen && "-translate-y-2 -rotate-45",
                  )}
                />
              </div>
            </button>
          </div>
        </nav>
      </header>

      {/* Full-screen Luxury Mobile Drawer */}
      <div
        aria-hidden={!menuOpen}
        className={cn(
          "fixed inset-0 z-40 flex flex-col bg-ink text-white transition-all duration-500 ease-site lg:hidden",
          menuOpen
            ? "opacity-100 pointer-events-auto"
            : "opacity-0 pointer-events-none translate-y-[-8px]",
        )}
      >
        <div className="flex flex-col justify-between h-full px-6 pt-24 pb-10 overflow-y-auto">
          {/* Navigation Links */}
          <div className="space-y-4">
            <p className="text-label font-semibold tracking-widest text-white/50 uppercase">Navigation</p>
            <ul className="space-y-2">
              {navLinks.map((link, idx) => (
                <li key={link.href} style={{ transitionDelay: `${idx * 40}ms` }}>
                  <a
                    href={link.href}
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center justify-between py-2.5 font-display text-display-sm font-bold text-white/90 hover:text-white"
                  >
                    <span>{link.label}</span>
                    <ArrowRightIcon className="size-5 text-white/40" />
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Quick Actions Drawer Bottom */}
          <div className="pt-8 border-t border-white/15 space-y-3">
            <p className="text-label font-semibold tracking-widest text-white/50 uppercase">Direct Access</p>
            <div className="grid gap-2.5 sm:grid-cols-2">
              <Link
                href="/r"
                onClick={() => setMenuOpen(false)}
                className="flex items-center justify-between p-4 rounded-xl bg-white text-ink font-bold text-body-sm shadow-md"
              >
                <span>Ask for help (Citizen)</span>
                <ArrowRightIcon className="size-4" />
              </Link>
              <Link
                href="/responder"
                onClick={() => setMenuOpen(false)}
                className="flex items-center justify-between p-4 rounded-xl border border-white/20 bg-white/10 font-bold text-body-sm text-white"
              >
                <span>Rescue Team App</span>
                <ArrowRightIcon className="size-4 text-white/60" />
              </Link>
              <Link
                href="/login"
                onClick={() => setMenuOpen(false)}
                className="flex items-center justify-between p-4 rounded-xl border border-white/20 bg-white/10 font-bold text-body-sm text-white"
              >
                <span>Control Room Login</span>
                <ArrowRightIcon className="size-4 text-white/60" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

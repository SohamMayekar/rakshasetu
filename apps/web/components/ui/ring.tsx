"use client";

// The check-in ring: how much of the current window is left before this team must be heard from.
// Calm until it's late; then "Contact overdue" in ink inversion (the attention treatment). The demo profile's
// fast clock is always said out loud on the ring.

import { useEffect, useState } from "react";

function mmss(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  return s >= 3600 ? `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function Ring({ due, windowMs, overdue, label = "check-in due", demo }: {
  due: string; windowMs: number; overdue?: boolean; label?: string; demo?: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const left = new Date(due).getTime() - now;
  const late = overdue || left <= 0;
  const frac = Math.max(0, Math.min(1, left / windowMs));
  const r = 9, c = 2 * Math.PI * r;
  return (
    <span className="inline-flex items-center gap-2">
      <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden>
        <circle cx="11" cy="11" r={r} fill="none" stroke="#e5e5e5" strokeWidth="3" />
        {!late && <circle cx="11" cy="11" r={r} fill="none" stroke="#111" strokeWidth="3" strokeDasharray={`${c * frac} ${c}`}
                          transform="rotate(-90 11 11)" strokeLinecap="round" />}
        {late && <circle cx="11" cy="11" r={r} fill="#111" />}
      </svg>
      {late ? <span className="rounded-full bg-ink px-2 py-0.5 text-xs font-medium text-paper">Contact overdue {mmss(-left)}</span>
            : <span className="tabular text-sm">{label} <b>{mmss(left)}</b></span>}
      {demo && <span className="text-[10px] text-ink-3">demo clock: 60× faster</span>}
    </span>
  );
}

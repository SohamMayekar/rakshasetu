"use client";

// Field pieces for the responder app: big type, buttons ≥ 64 px in the bottom third, Hindi + English labels,
// and the tap status line ("Saved on phone → Sent 02:32") with its 10-second Undo.

import { useEffect, useState } from "react";

import { type Tap, subscribe, taps, undo } from "@/lib/outbox";

export function BigButton({ children, onClick, variant = "primary", disabled }: {
  children: React.ReactNode; onClick?: () => void; variant?: "primary" | "secondary"; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
            className={`flex min-h-16 w-full items-center justify-center rounded-2xl px-5 text-lg font-semibold disabled:opacity-40 ${
              variant === "primary" ? "bg-ink text-paper active:bg-ink-2" : "border-2 border-ink bg-paper text-ink active:bg-wash"}`}>
      {children}
    </button>
  );
}

export function useTaps(): Tap[] {
  const [list, setList] = useState<Tap[]>([]);
  useEffect(() => {
    const update = () => setList(taps());
    update();
    const off = subscribe(update);
    const t = setInterval(update, 1000);
    return () => { off(); clearInterval(t); };
  }, []);
  return list;
}

const hhmm = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });

export function TapStatus({ caseId }: { caseId: number }) {
  const list = useTaps().filter((t) => t.caseId === caseId).slice(-2);
  const [, tick] = useState(0);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 500); return () => clearInterval(t); }, []);
  if (!list.length) return null;
  return (
    <ul className="space-y-1.5">
      {list.map((t) => {
        const wait = Math.ceil((t.sendAfter - Date.now()) / 1000);
        return (
          <li key={t.id} className="flex items-center justify-between gap-3 rounded-xl bg-wash px-3 py-2 text-sm">
            <span><b>{t.label}</b> · {t.state === "sent" ? <>Sent {hhmm(t.sentAt!)}</> : t.state === "failed" ? <>not accepted: {t.error}</>
                                                          : wait > 0 ? <>Saved on phone · sending in {wait} s</> : <>Saved on phone · sending…</>}</span>
            {t.state === "saved" && wait > 0 && <button onClick={() => undo(t.id)} className="min-h-11 rounded-lg border border-ink px-4 font-semibold">Undo</button>}
          </li>
        );
      })}
    </ul>
  );
}

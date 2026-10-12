"use client";

// PRD P1 #7: keep the team phone's screen on while the team is on its way or on scene (acknowledged → rescued
// or released). The browser drops the lock whenever the page is hidden, so it is asked for again on return.
// Where Wake Lock isn't supported (or is refused) nothing breaks: the screen just sleeps as usual.

import { useEffect } from "react";

type Sentinel = { release: () => Promise<void>; released: boolean };

export function useWakeLock(active: boolean) {
  useEffect(() => {
    if (!active || typeof navigator === "undefined" || !("wakeLock" in navigator)) return;
    let lock: Sentinel | null = null;
    let gone = false;
    const ask = async () => {
      if (gone || document.visibilityState !== "visible" || (lock && !lock.released)) return;
      try { lock = await (navigator as unknown as { wakeLock: { request: (t: "screen") => Promise<Sentinel> } }).wakeLock.request("screen"); }
      catch { /* refused (battery saver, policy): fine */ }
    };
    ask();
    document.addEventListener("visibilitychange", ask);
    return () => { gone = true; document.removeEventListener("visibilitychange", ask); lock?.release().catch(() => {}); };
  }, [active]);
}

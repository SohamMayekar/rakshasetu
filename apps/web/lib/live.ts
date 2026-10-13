"use client";

// Live updates (PRD F-C10): one WebSocket from `since`, reconnecting with the last seq seen, so a dropped
// connection loses nothing. Events are handed over in 1-second frames (F-C5: batched render), never one by one.
//
// The socket only works where something can hold it. Behind a proxy that forwards HTTP but not the
// upgrade (a deployed front end, the tunnel) it never opens, so after two failed attempts we poll
// GET /v1/events?since= instead: the same scoped envelopes through the same listener, 2.5 s apart.

import { useEffect, useRef, useState } from "react";

export type Envelope = { seq: number; type: string; incident_id: number | null; at: string; data: Record<string, unknown> };
export type LiveState = { connected: boolean; pausedSince: string | null };

const POLL_MS = 2500;

export function useLive(incident: string, since: number | null, onFrame: (events: Envelope[]) => void): LiveState {
  const [state, setState] = useState<LiveState>({ connected: false, pausedSince: null });
  const handler = useRef(onFrame);
  handler.current = onFrame;

  useEffect(() => {
    if (since == null) return;
    let cursor = since;
    let ws: WebSocket | null = null;
    let closed = false;
    let failures = 0;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let poller: ReturnType<typeof setInterval> | undefined;
    let pending: Envelope[] = [];
    const frame = setInterval(() => {
      if (pending.length) { const batch = pending; pending = []; handler.current(batch); }
    }, 1000);

    const collect = (env: Envelope) => {
      if (env.type === "hello" || env.type === "ping") return;
      if (env.type === "reset") { location.reload(); return; }   // the log was reset (demo reset): start over
      if (env.seq > cursor) { cursor = env.seq; pending.push(env); }
    };

    const poll = async () => {
      try {
        const r = await fetch(`/v1/events?incident=${encodeURIComponent(incident)}&since=${cursor}`, { credentials: "same-origin" });
        if (!r.ok) return;
        (await r.json() as Envelope[]).forEach(collect);
        setState({ connected: true, pausedSince: null });
      } catch { /* the next tick tries again */ }
    };

    const startPolling = () => {
      if (poller) return;
      void poll();
      poller = setInterval(poll, POLL_MS);
    };

    const open = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/v1/ws?incident=${encodeURIComponent(incident)}&since=${cursor}`);
      ws.onopen = () => { failures = 0; setState({ connected: true, pausedSince: null }); };
      ws.onmessage = (m) => collect(JSON.parse(m.data) as Envelope);
      ws.onclose = () => {
        setState((s) => ({ connected: false, pausedSince: s.pausedSince ?? new Date().toISOString() }));
        if (closed) return;
        failures += 1;
        if (failures >= 2) { startPolling(); return; }   // no socket to be had here: poll instead
        retry = setTimeout(open, 2000);
      };
    };
    open();
    return () => { closed = true; clearInterval(frame); clearInterval(poller); clearTimeout(retry); ws?.close(); };
  }, [incident, since]);

  return state;
}

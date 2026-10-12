"use client";

// Live updates (PRD F-C10): one WebSocket from `since`, reconnecting with the last seq seen, so a dropped
// connection loses nothing. Events are handed over in 1-second frames (F-C5: batched render), never one by one.

import { useEffect, useRef, useState } from "react";

export type Envelope = { seq: number; type: string; incident_id: number | null; at: string; data: Record<string, unknown> };
export type LiveState = { connected: boolean; pausedSince: string | null };

export function useLive(incident: string, since: number | null, onFrame: (events: Envelope[]) => void): LiveState {
  const [state, setState] = useState<LiveState>({ connected: false, pausedSince: null });
  const handler = useRef(onFrame);
  handler.current = onFrame;

  useEffect(() => {
    if (since == null) return;
    let cursor = since;
    let ws: WebSocket | null = null;
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let pending: Envelope[] = [];
    const frame = setInterval(() => {
      if (pending.length) { const batch = pending; pending = []; handler.current(batch); }
    }, 1000);

    const open = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/v1/ws?incident=${encodeURIComponent(incident)}&since=${cursor}`);
      ws.onopen = () => setState({ connected: true, pausedSince: null });
      ws.onmessage = (m) => {
        const env = JSON.parse(m.data) as Envelope;
        if (env.type === "hello" || env.type === "ping") return;
        if (env.type === "reset") { location.reload(); return; }   // the log was reset (demo reset): start over
        if (env.seq > cursor) { cursor = env.seq; pending.push(env); }
      };
      ws.onclose = () => {
        setState((s) => ({ connected: false, pausedSince: s.pausedSince ?? new Date().toISOString() }));
        if (!closed) retry = setTimeout(open, 2000);
      };
    };
    open();
    return () => { closed = true; clearInterval(frame); clearTimeout(retry); ws?.close(); };
  }, [incident, since]);

  return state;
}

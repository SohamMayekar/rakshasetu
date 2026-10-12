"use client";

// Every desk-side screen sits in this shell (m60): the sidebar on the canvas, the page beside it. It reads who
// is signed in unless the page already has it, so the sidebar can offer only what this role may open.

import { type ReactNode, useEffect, useState } from "react";

import { PhoneBar, Sidebar } from "@/components/shell/Sidebar";
import { api, type Me } from "@/lib/api";

export function AppShell({ me: given, compact = false, children }: { me?: Me | null; compact?: boolean; children: ReactNode }) {
  const [fetched, setFetched] = useState<Me | null>(null);
  useEffect(() => { if (given === undefined) api<Me>("/v1/me").then(setFetched).catch(() => {}); }, [given]);
  const me = given === undefined ? fetched : given;
  return (
    <div className="flex min-h-dvh bg-canvas">
      <Sidebar me={me} compact={compact} />
      <div className="min-w-0 flex-1"><PhoneBar me={me} />{children}</div>
    </div>
  );
}

// The standard page body beside the sidebar: generous margins, a readable width.
export function Page({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return <main className={`mx-auto w-full px-4 pb-16 pt-6 md:px-8 md:pt-10 ${wide ? "max-w-6xl" : "max-w-5xl"}`}>{children}</main>;
}

"use client";

// The frame for the desk's own pages (Cases, Teams, Alerts, Sheets): the sidebar and the page title. These pages
// are national: they list every incident this person may see. Signed out → the sign-in page.

import { type ReactNode, useEffect, useState } from "react";

import { AppShell, Page } from "@/components/shell/AppShell";
import { PageHeader } from "@/components/ui";
import { api, ApiError, type Me } from "@/lib/api";

export function useMe(): Me | null {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    api<Me>("/v1/me").then(setMe).catch((e) => { if (e instanceof ApiError && e.status === 401) location.href = "/login"; });
  }, []);
  return me;
}

export function IncidentPage({ me, title, sub, aside, children }: {
  me: Me | null; title: string; sub: string; aside?: ReactNode; children: ReactNode;
}) {
  return (
    <AppShell me={me}>
      <Page wide>
        <PageHeader title={title} sub={sub} aside={aside} />
        <div className="mt-6">{children}</div>
      </Page>
    </AppShell>
  );
}

// A row of filter buttons, each with its count; the current one is ink. Used by Cases and Teams.
export function Filters<K extends string>({ value, onChange, items }: {
  value: K; onChange: (k: K) => void; items: { key: K; label: string; count: number }[];
}) {
  return (
    <div className="flex flex-wrap gap-1.5" role="tablist">
      {items.map((it) => (
        <button key={it.key} role="tab" aria-selected={value === it.key} onClick={() => onChange(it.key)}
                className={`inline-flex h-9 items-center gap-2 rounded-full px-3.5 text-body transition-colors ${value === it.key
                  ? "bg-ink text-paper" : "bg-paper text-ink-2 shadow-[var(--shadow-card)] hover:text-ink"}`}>
          {it.label}<span className={`tabular text-small ${value === it.key ? "text-paper/70" : "text-ink-3"}`}>{it.count}</span>
        </button>
      ))}
    </div>
  );
}

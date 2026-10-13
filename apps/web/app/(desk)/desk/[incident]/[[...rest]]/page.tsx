"use client";

// There is one desk, for the whole country. The old per-disaster addresses (/desk/BR, /desk/BR/teams?…) still
// work for anyone who saved them: they land on the same page of the one desk, keeping the query (?case=…).

import { use, useEffect } from "react";

export default function OldDeskAddress({ params }: { params: Promise<{ incident: string; rest?: string[] }> }) {
  const { rest } = use(params);
  const page = rest?.[0] && ["cases", "teams", "alerts", "sheets"].includes(rest[0]) ? `/${rest[0]}` : "";
  useEffect(() => { location.replace(`/desk${page}${location.search}`); }, [page]);
  return <p className="p-6 text-body text-ink-2">Opening the desk…</p>;
}

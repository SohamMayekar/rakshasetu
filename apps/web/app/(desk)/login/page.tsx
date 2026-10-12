"use client";

// "Sign in as…" (PRD F-C9): the demo's synthetic users, one tap each. Local listener + DEMO_MODE only; the
// API answers 404 elsewhere, and then this page asks for a username and password instead.

import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";

type Pick = { username: string; name: string; role: string; role_label: string; team: string | null };

const HOME: Record<string, (incident: string) => string> = {
  call_taker: (i) => `/desk/${i}`, duty_officer: (i) => `/desk/${i}`, incharge: (i) => `/desk/${i}`,
  admin: (i) => `/desk/${i}`, team_lead: () => "/responder", seoc_viewer: () => "/",
};

async function enter(username: string, password?: string) {
  await api("/v1/auth/login", { method: "POST", json: password ? { username, password } : { username } });
  const me = await api<{ user: { role: string }; incidents: { code: string }[] }>("/v1/me");
  location.href = (HOME[me.user.role] ?? (() => "/"))(me.incidents[0]?.code ?? "BR");
}

export default function Login() {
  const [users, setUsers] = useState<Pick[] | null>(null);
  const [picker, setPicker] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Pick[]>("/v1/auth/users").then(setUsers).catch(() => setPicker(false));
  }, []);

  const initials = (n: string) => n.replace(/[^A-Za-z ]/g, " ").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
  return (
    <main className="grid min-h-screen place-items-center bg-canvas px-4 py-10">
      <Card className="w-full max-w-xl p-6 md:p-8">
        <div className="flex items-center gap-2.5"><Mark className="size-8 text-ink" /><span className="text-[17px] font-semibold tracking-tight">RakshaSetu</span></div>
        <h1 className="mt-6 text-[26px] font-semibold tracking-tight">Sign in</h1>
        {picker ? (
          <>
            <p className="mt-1 text-sm text-ink-2">Demo users (synthetic). Each sees only their incident and district.</p>
            <ul className="mt-5 space-y-1">
              {(users ?? []).map((u) => (
                <li key={u.username}>
                  <button onClick={() => enter(u.username).catch((e) => setError(String(e.message)))}
                          className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left transition-colors hover:bg-wash">
                    <span className="grid size-10 shrink-0 place-items-center rounded-full bg-wash text-sm font-semibold text-ink-2" aria-hidden>{initials(u.name)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{u.name}</span>
                      <span className="block truncate text-sm text-ink-3">{u.role_label}{u.team ? ` · ${u.team}` : ""}</span>
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-ink-3" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <form className="mt-6 space-y-3" onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            enter(String(f.get("username")), String(f.get("password"))).catch((err) => setError(String(err.message)));
          }}>
            <input name="username" placeholder="Username" autoComplete="username" className="h-11 w-full rounded-xl border border-line px-3" />
            <input name="password" type="password" placeholder="Password" autoComplete="current-password" className="h-11 w-full rounded-xl border border-line px-3" />
            <Button variant="primary" type="submit">Sign in</Button>
          </form>
        )}
        {error && <p className="mt-4 text-sm text-ink">{error}</p>}
      </Card>
    </main>
  );
}

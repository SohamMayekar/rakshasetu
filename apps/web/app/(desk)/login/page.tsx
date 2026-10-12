"use client";

// "Sign in as…" (PRD F-C9): the demo's synthetic users, one tap each. Local listener + DEMO_MODE only; the
// API answers 404 elsewhere, and then this page asks for a username and password instead.

import { useEffect, useState } from "react";

import { Button } from "@/components/ui";
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

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <p className="text-sm font-semibold text-ink-2">RakshaSetu</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight">Sign in</h1>
      {picker ? (
        <>
          <p className="mt-1 text-sm text-ink-2">Demo users (synthetic). Each sees only their incident and district.</p>
          <ul className="mt-6 divide-y divide-line rounded-xl border border-line">
            {(users ?? []).map((u) => (
              <li key={u.username}>
                <button onClick={() => enter(u.username).catch((e) => setError(String(e.message)))}
                        className="flex w-full items-baseline justify-between gap-4 px-4 py-3 text-left hover:bg-wash">
                  <span><span className="font-medium">{u.name}</span>{u.team && <span className="text-ink-3"> · {u.team}</span>}</span>
                  <span className="text-sm text-ink-2">{u.role_label}</span>
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
          <input name="username" placeholder="Username" autoComplete="username" className="h-11 w-full rounded-lg border border-line px-3" />
          <input name="password" type="password" placeholder="Password" autoComplete="current-password" className="h-11 w-full rounded-lg border border-line px-3" />
          <Button variant="primary" type="submit">Sign in</Button>
        </form>
      )}
      {error && <p className="mt-4 text-sm text-ink">{error}</p>}
    </main>
  );
}

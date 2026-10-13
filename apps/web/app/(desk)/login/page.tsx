"use client";

// Sign in with a username and a password. The demo's one-tap choices live on the door (/) — this page is the
// plain way in for anyone else (and the way back after a sign-out).

import { useState } from "react";

import { Mark } from "@/components/shell/Sidebar";
import { Button, Card } from "@/components/ui";
import { api } from "@/lib/api";

const HOME: Record<string, (incident: string) => string> = {
  call_taker: (i) => `/desk/${i}`, duty_officer: (i) => `/desk/${i}`, incharge: (i) => `/desk/${i}`,
  admin: () => "/", team_lead: () => "/responder", seoc_viewer: () => "/",
};

async function enter(username: string, password: string) {
  await api("/v1/auth/login", { method: "POST", json: { username, password } });
  const me = await api<{ user: { role: string }; incidents: { code: string }[] }>("/v1/me");
  location.href = me.incidents[0] ? (HOME[me.user.role] ?? (() => "/"))(me.incidents[0].code) : "/";
}

export default function Login() {
  const [error, setError] = useState<string | null>(null);

  return (
    <main className="grid min-h-dvh place-items-center bg-canvas px-4 py-10">
      <Card className="w-full max-w-xl p-6 md:p-8">
        <div className="flex items-center gap-2.5"><Mark className="size-8 text-ink" /><span className="text-heading font-semibold tracking-tight">RakshaSetu</span></div>
        <h1 className="mt-6 text-display font-semibold tracking-tight">Sign in</h1>
        <form className="mt-6 space-y-3" onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          enter(String(f.get("username")), String(f.get("password"))).catch((err) => setError(String(err.message)));
        }}>
          <input name="username" placeholder="Username" autoComplete="username" className="h-11 w-full rounded-xl border border-line px-3" />
          <input name="password" type="password" placeholder="Password" autoComplete="current-password" className="h-11 w-full rounded-xl border border-line px-3" />
          <Button variant="primary" type="submit">Sign in</Button>
        </form>
        {error && <p className="mt-4 text-body text-ink">{error}</p>}
        <p className="mt-6 text-small text-ink-2">Not sure who you are? The door at <a className="underline underline-offset-4" href="/?door=1">the front</a> has the three ways in.</p>
      </Card>
    </main>
  );
}

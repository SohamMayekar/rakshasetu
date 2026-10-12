// Home. The Incidents screen (PRD F-C1) arrives in m48; until then, sign in and go to your desk.

export default function Home() {
  return (
    <main className="mx-auto max-w-xl p-10">
      <h1 className="text-3xl font-semibold tracking-tight">RakshaSetu</h1>
      <p className="mt-2 text-ink-2">Never lost. Never doubled. Never stale.</p>
      <p className="mt-8"><a className="underline underline-offset-2" href="/login">Sign in</a></p>
    </main>
  );
}

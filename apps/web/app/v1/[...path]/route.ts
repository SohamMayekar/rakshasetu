import type { NextRequest } from "next/server";

// Proxy /v1/* to the API (Render in production, localhost in development).
//
// Why not a rewrite: a rewrite in next.config.ts becomes an edge route on Vercel and runs BEFORE the
// middleware, and a NextResponse.rewrite() to another origin loses the request-header override on the
// way out. Either way the API receives the call without `x-rs-listener: local`, and the desk's write
// endpoints (assignments, rescues, dispatch, metrics, escalations) answer 404 — they exist only on the
// local listener (rule R18). Doing the call here keeps the header under our control.
//
// In the compose stack Caddy routes /v1/* to the API before Next sees it, so this never runs there.
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8000";

// Set by the upstream response, and not ours to repeat.
const DROPPED = ["content-encoding", "content-length", "transfer-encoding", "connection"];

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = new URL(`/v1/${path.join("/")}`, apiOrigin);
  target.search = request.nextUrl.search;

  const headers = new Headers(request.headers);
  headers.set("x-rs-listener", "local");
  headers.delete("host");              // the API is a different host
  headers.delete("content-length");    // the body is forwarded as a stream: its length is not known here

  const body = request.method === "GET" || request.method === "HEAD" ? undefined : request.body;
  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body,
    redirect: "manual",
    duplex: "half",
  } as RequestInit);

  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (!DROPPED.includes(lower) && lower !== "set-cookie") out.set(key, value);
  });
  const setCookies = upstream.headers.getSetCookie?.() ?? [];
  if (setCookies.length) {
    for (const cookie of setCookies) out.append("set-cookie", cookie);
  } else if (upstream.headers.get("set-cookie")) {
    out.append("set-cookie", upstream.headers.get("set-cookie") as string);
  }

  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const runtime = "nodejs";   // streams request and response bodies without an edge-runtime ceiling

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const HEAD = proxy;
export const OPTIONS = proxy;

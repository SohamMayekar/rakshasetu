import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// The API runs on another origin (Render), and /v1/* has to be proxied from here rather than from
// next.config.ts: Vercel turns those rewrites into edge routes, which run BEFORE this middleware, so
// the request would arrive without the listener header. With no `x-rs-listener: local` the desk's
// write endpoints answer 404 (rule R18) — the desk has to be reachable through this proxy.
//
// Everything else Caddy does in the compose stack (infra/caddy) is unchanged: there, Caddy stamps the
// header and Next is never asked for /v1/*.
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8000";

export function middleware(request: NextRequest) {
  const headers = new Headers(request.headers);
  if (!headers.has("x-rs-listener")) {
    headers.set("x-rs-listener", "local");
  }

  const target = new URL(request.nextUrl.pathname + request.nextUrl.search, apiOrigin);
  return NextResponse.rewrite(target, { request: { headers } });
}

export const config = {
  matcher: ["/v1/:path*"],
};

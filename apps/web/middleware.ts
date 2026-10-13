import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// The listener rule (R18) is enforced in the API, not here: Caddy stamps `x-rs-listener` on the two
// listeners it serves, and the API treats a request without it as public. /v1/* is proxied to the API
// by app/v1/[...path]/route.ts, which sets the header for a deployed front end; this stays as the
// second half of the same idea (a header the browser cannot choose for itself).
export function middleware(request: NextRequest) {
  const headers = new Headers(request.headers);
  if (!headers.has("x-rs-listener")) {
    headers.set("x-rs-listener", "local");
  }
  return NextResponse.next({
    request: {
      headers,
    },
  });
}

export const config = {
  matcher: ["/v1/:path*"],
};

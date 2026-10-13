import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const requestHeaders = new Headers(request.headers);
  if (!requestHeaders.has("x-rs-listener")) {
    requestHeaders.set("x-rs-listener", "local");
  }
  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: ["/v1/:path*"],
};

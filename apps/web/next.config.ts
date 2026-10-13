import type { NextConfig } from "next";

// /v1/* is proxied to the API by the middleware (apps/web/middleware.ts), not from here: a rewrite in
// this file becomes an edge route on Vercel and would run before the middleware, which is what sets
// `x-rs-listener`. Caddy does the same job in the compose stack, where Next never sees /v1/*.
const nextConfig: NextConfig = {
  poweredByHeader: false,
};

export default nextConfig;

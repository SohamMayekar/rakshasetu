import type { NextConfig } from "next";

// In docker compose, Caddy routes /v1/* to the API before requests reach Next.
// The rewrite below only matters when the web app runs alone (`npm run dev`).
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${apiOrigin}/v1/:path*` }];
  },
};

export default nextConfig;

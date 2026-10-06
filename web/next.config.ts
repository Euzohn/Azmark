import type { NextConfig } from "next";

// Same-origin proxy: the browser only talks to the web server, which forwards
// /api/* to the backend over the internal Docker network (no public API port).
// In docker compose this is set to http://api:8000 at build time.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

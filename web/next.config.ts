import type { NextConfig } from "next";

// Same-origin proxy: the browser only talks to the web server, which forwards
// /api/* to the backend over the internal Docker network (no public API port).
// In docker compose this is set to http://api:8000 at build time.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

// Next 16 buffers proxied request bodies (10MB by default) and silently
// truncates anything larger, resetting the upstream socket — a 12.9MB photo
// upload 500'd here without ever reaching the API. Keep the buffer above the
// backend's MAX_ATTACHMENT_BYTES cap so oversized files arrive intact and get
// a clean 413 instead. Build-time value like API_INTERNAL_URL; compose passes
// it as a build arg.
const MAX_ATTACHMENT_BYTES = Number(process.env.MAX_ATTACHMENT_BYTES ?? 20971520);
const PROXY_BODY_HEADROOM_BYTES = 5 * 1024 * 1024;

const nextConfig: NextConfig = {
  experimental: {
    proxyClientMaxBodySize: MAX_ATTACHMENT_BYTES + PROXY_BODY_HEADROOM_BYTES,
  },
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

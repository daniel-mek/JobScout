import type { NextConfig } from "next";

const api = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    // Vercel Services owns ingress there; bindings exist only at runtime.
    if (process.env.VERCEL && !process.env.API_INTERNAL_URL) return [];
    return [{ source: "/backend/:path*", destination: `${api}/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
        ],
      },
    ];
  },
};
export default config;

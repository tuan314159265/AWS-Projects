import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/stats", destination: "http://localhost:8000/stats" },
      { source: "/health", destination: "http://localhost:8000/health" },
      { source: "/articles/:path*", destination: "http://localhost:8000/articles/:path*" },
      { source: "/models", destination: "http://localhost:8000/models" },
      { source: "/search", destination: "http://localhost:8000/search" },
      { source: "/pipeline/:path*", destination: "http://localhost:8000/pipeline/:path*" },
      { source: "/sources", destination: "http://localhost:8000/sources" },
      { source: "/monitor/:path*", destination: "http://localhost:8000/monitor/:path*" },
    ];
  },
};

export default nextConfig;
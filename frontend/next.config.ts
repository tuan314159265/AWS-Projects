import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // API calls go through api.ts which reads NEXT_PUBLIC_API_URL
  // - Local dev: export NEXT_PUBLIC_API_URL=http://localhost:8000
  // - AWS: set to API Gateway URL
};

export default nextConfig;

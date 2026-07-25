import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/search", destination: "https://2ohkfkehda.execute-api.ap-southeast-2.amazonaws.com/prod/query" }
    ];
  },
};

export default nextConfig;
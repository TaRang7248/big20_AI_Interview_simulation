import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // FastAPI 백엔드로 API 프록시
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
      { source: "/ws/:path*", destination: `${backendUrl}/ws/:path*` },
      { source: "/emotion", destination: `${backendUrl}/emotion` },
      { source: "/health", destination: `${backendUrl}/health` },
    ];
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // React Strict Mode 비활성화 — 개발 모드에서 컴포넌트 이중 마운트(mount→unmount→remount)로
  // 카메라/WebSocket/SpeechRecognition이 두 번 초기화되어 불안정해지는 문제 방지
  // (프로덕션에는 영향 없음 — 프로덕션은 항상 single mount)
  reactStrictMode: false,
  // FastAPI 백엔드로 API 프록시
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${backendUrl}/api/:path*` },
      { source: "/ws/:path*", destination: `${backendUrl}/ws/:path*` },
      { source: "/health", destination: `${backendUrl}/health` },
    ];
  },
};

export default nextConfig;

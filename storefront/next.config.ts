import type { NextConfig } from "next";

// Ürün görselleri backend'in /storage mount'undan gelir; tarayıcı aynı origin'den
// /storage/* ister, Next sunucusu backend'e proxy'ler (dev'de ve Caddy arkasında
// aynı şekilde çalışır — CORS gerekmez).
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/storage/:path*",
        destination: `${BACKEND_URL}/storage/:path*`,
      },
    ];
  },
};

export default nextConfig;

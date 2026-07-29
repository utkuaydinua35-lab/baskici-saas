import type { NextConfig } from "next";

// Ürün görselleri backend'in /storage mount'undan gelir; tarayıcı aynı origin'den
// /storage/* ister, Next sunucusu backend'e proxy'ler (dev'de ve Caddy arkasında
// aynı şekilde çalışır — CORS gerekmez).
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

// Güvenlik başlıkları — nginx'te de tanımlı; burada da olması vitrinin
// nginx'siz (dev/başka ortam) çalıştırıldığında korumasız kalmasını önler.
const SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  // Tema editörü önizlemeyi kendi iframe'inde açtığından SAMEORIGIN
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Sipariş takip token'ı URL'de taşınır — dış sitelere tam adres sızmasın
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,   // "X-Powered-By: Next.js" sürüm bilgisi sızdırmasın
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
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

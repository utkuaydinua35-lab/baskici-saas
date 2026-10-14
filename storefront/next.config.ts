import type { NextConfig } from "next";

// Ürün görselleri backend'in /storage mount'undan gelir; tarayıcı aynı origin'den
// /storage/* ister, Next sunucusu backend'e proxy'ler (dev'de ve Caddy arkasında
// aynı şekilde çalışır — CORS gerekmez).
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

// Panelin canlı önizlemesi vitrini iframe'e gömer. Panel FARKLI bir alt alan
// adında olduğu için X-Frame-Options: SAMEORIGIN bunu reddediyordu ve XFO birden
// çok origin'e izin veremiyor → CSP frame-ancestors kullanılıyor.
// PANEL_ORIGINS: boşlukla ayrılmış panel adresleri (.env'den değiştirilebilir).
const PANEL_ORIGINS =
  process.env.PANEL_ORIGINS ||
  "https://magazapanel.bernzcompany.com https://studio.bernzcompany.com";

// Güvenlik başlıkları — TEK KAYNAK burası. Eskiden nginx de aynılarını
// basıyordu ve her başlık yanıtta iki kez gidiyordu; nginx'teki kopyalar
// kaldırıldı. Her kiracı alan adı otomatik olarak bunları alır.
const SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  // CSP — bilinçli olarak DAR:
  //   frame-ancestors  clickjacking: yalnız kendi panelimiz gömebilir
  //   object-src none  eklenti (<object>/<embed>) yüzeyi — vitrinde hiç yok
  //   base-uri self    <base> etiketiyle tüm göreli adresleri başka alana
  //                    çevirme saldırısı — vitrin <base> kullanmıyor
  // script-src YOK, BİLEREK: mağaza sahibi panelden özel kod yapıştırabiliyor
  // (indirim çarkı, çıkış penceresi, üçüncü taraf araçlar). Kaynak listesi
  // o özelliği sessizce bozar. Sıkı script-src ancak özel kod kısıtlanırsa
  // mümkün — bu bir ürün kararı (dış güvenlik incelemesi, 22.09.2026).
  { key: "Content-Security-Policy",
    value: `frame-ancestors 'self' ${PANEL_ORIGINS}; object-src 'none'; base-uri 'self'` },
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Sipariş takip token'ı URL'de taşınır — dış sitelere tam adres sızmasın
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  poweredByHeader: false,   // "X-Powered-By: Next.js" sürüm bilgisi sızdırmasın
  experimental: {
    // CSS sayfanın içinde gelir (~20 KB sıkıştırılmış). Ayrı .css dosyası
    // ilk görüntüyü bekleten bir istek daha demekti (telefonda ~470 ms,
    // Lighthouse "oluşturmayı engelleyen kaynak"). Ziyaretçilerin çoğu reklamdan
    // İLK KEZ geldiği için önbellekli dosyanın kazancı yok denecek kadar az.
    inlineCss: true,
  },
  // Shopify'dan kalan sabit adresler (ürün/koleksiyon: app/products, app/collections).
  // Sorgu dizesi (fbclid, utm_*, q) Next tarafından hedefe aynen taşınır.
  async redirects() {
    return [
      { source: "/collections", destination: "/urunler", permanent: true },
      { source: "/search", destination: "/urunler", permanent: true },
      { source: "/cart", destination: "/sepet", permanent: true },
      { source: "/account", destination: "/hesap", permanent: true },
      { source: "/account/:yol*", destination: "/hesap", permanent: true },
      { source: "/policies/privacy-policy", destination: "/gizlilik", permanent: true },
      { source: "/policies/refund-policy", destination: "/iade", permanent: true },
      { source: "/policies/terms-of-service", destination: "/mesafeli-satis", permanent: true },
      { source: "/policies/:yol*", destination: "/iade", permanent: true },
      { source: "/pages/gizlilik-politikasi", destination: "/gizlilik", permanent: true },
      { source: "/pages/mesafeli-satis-sozlesmesi", destination: "/mesafeli-satis", permanent: true },
      { source: "/pages/:yol(iade.*|degisim.*)", destination: "/iade", permanent: true },
      { source: "/blogs/:yol*", destination: "/blog", permanent: true },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    return [
      {
        source: "/storage/:path*",
        destination: `${BACKEND_URL}/storage/:path*`,
      },
      // RFC 9116 güvenlik bildirim dosyası — mağazanın kendi e-postasıyla
      { source: "/.well-known/security.txt", destination: "/api/security-txt" },
      // app/favicon.ico Next'te özel dosya adı (klasör olarak rota açılmıyor)
      { source: "/favicon.ico", destination: "/api/simge" },
      // Ürün akışları (Meta katalogu / Google Merchant) — bkz. app/api/feed
      { source: "/feed/meta.xml", destination: "/api/feed/meta" },
      { source: "/feed/google.xml", destination: "/api/feed/google" },
    ];
  },
};

export default nextConfig;

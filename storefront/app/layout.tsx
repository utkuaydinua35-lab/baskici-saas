import type { Metadata } from "next";
import { DM_Sans, Inter, Playfair_Display, Poppins } from "next/font/google";
import "./globals.css";
import { CartProvider } from "@/lib/cart";
import { getThemePayload } from "@/lib/theme";
import { getCollections } from "@/lib/api";
import Header from "@/components/Header";
import AnnouncementBar from "@/components/AnnouncementBar";
import CartDrawer from "@/components/CartDrawer";
import Pixels from "@/components/Pixels";
import CustomCode from "@/components/CustomCode";
import NewsletterForm from "@/components/NewsletterForm";
import WhatsAppButton from "@/components/WhatsAppButton";
import CouponFromUrl from "@/components/CouponFromUrl";
import LockScreen from "@/components/LockScreen";
import PreviewBridge from "@/components/PreviewBridge";
import CopyGuard from "@/components/CopyGuard";
import SupportChat from "@/components/SupportChat";
import Presence from "@/components/Presence";
import { cookies, headers } from "next/headers";
import { Suspense } from "react";

// Font preset'leri — hepsi değişken olarak yüklenir, tema seçileni uygular.
const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter" });
const poppins = Poppins({ subsets: ["latin", "latin-ext"], weight: ["400", "500", "600", "700"], variable: "--font-poppins" });
const playfair = Playfair_Display({ subsets: ["latin", "latin-ext"], variable: "--font-playfair" });
const dmSans = DM_Sans({ subsets: ["latin", "latin-ext"], variable: "--font-dm-sans" });

const FONT_VAR: Record<string, string> = {
  inter: "var(--font-inter)",
  poppins: "var(--font-poppins)",
  playfair: "var(--font-playfair)",
  "dm-sans": "var(--font-dm-sans)",
};

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001";

// "telefon kılıfı" → "Telefon Kılıfı". Türkçe yerel ayarla: "istanbul"un
// "Istanbul" değil "İstanbul" olması için (bkz. Türkçe İ tuzağı).
function basHarfler(metin: string): string {
  return metin.split(" ").map((k) => k ? k[0].toLocaleUpperCase("tr") + k.slice(1) : k).join(" ");
}

export async function generateMetadata(): Promise<Metadata> {
  const { store_name, theme, isletme } = await getThemePayload();
  // metadataBase İSTEĞİN host'undan kurulur — favicon /storage yolu hangi
  // domain'den girildiyse oraya çözülür (App Router manuel <head>'i attığı
  // için favicon YALNIZCA metadata üzerinden basılabiliyor).
  let base: URL;
  try {
    const host = (await headers()).get("host") || "";
    const proto = host.startsWith("localhost") || host.startsWith("127.") ? "http" : "https";
    base = host ? new URL(`${proto}://${host}`) : new URL(SITE_URL);
  } catch {
    base = new URL(SITE_URL);
  }
  return {
    metadataBase: base,
    // Başlık ve açıklama MAĞAZA AYARINDAN. Eskiden "— Telefon Kılıfları" ve
    // BERNZ'in tanıtım cümlesi her mağazanın SEO'suna sabit yazılıydı.
    title: {
      default: isletme.urun_turu ? `${store_name} — ${basHarfler(isletme.urun_turu)}` : store_name,
      template: `%s | ${store_name}`,
    },
    description: isletme.tanitim || `${store_name} online mağazası.`,
    ...(theme.favicon_url
      ? { icons: { icon: [{ url: theme.favicon_url }], apple: [{ url: theme.favicon_url }] } }
      : {}),
  };
}

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [payload, navCollections] = await Promise.all([getThemePayload(), getCollections()]);
  const { store_name, theme, contact, pixels: payloadPixels, pages = [], custom_code } = payload;
  const fontFamily = FONT_VAR[theme.font] || FONT_VAR.inter;
  const year = new Date().getFullYear();
  const instagram = (theme.footer.instagram || contact.instagram || "").replace(/^@/, "");

  // Kiralama: abonelik askıda → yalnız bakım ekranı. Ödeme yapıldığı anda
  // (en geç tema önbelleğinin 60 sn'si içinde) site kaldığı yerden açılır.
  // Muafiyet: ödemesi yapılmış müşterinin sipariş takibi ve ödeme dönüşü
  // bakımdan etkilenmez — backend uçları zaten token ile çalışıyor.
  const yol = payload.bakimda ? ((await headers()).get("x-vitrin-yol") || "") : "";
  const bakimdanMuaf = yol.startsWith("/siparis/") || yol.startsWith("/odeme/sonuc");
  if (payload.bakimda && !bakimdanMuaf) {
    return (
      <html lang="tr" className={`${inter.variable} h-full antialiased`}>
        <body className="min-h-full flex items-center justify-center bg-zinc-50 text-zinc-900 p-6">
          <main className="max-w-sm text-center">
            <div className="text-4xl mb-4" aria-hidden="true">🛠️</div>
            <h1 className="text-xl font-semibold">Kısa bir bakımdayız</h1>
            <p className="mt-2 text-sm text-zinc-600">
              Mağazamız şu anda hizmet vermiyor. Lütfen daha sonra tekrar deneyin.
            </p>
            <p className="mt-4 text-xs text-zinc-500">
              Siparişiniz varsa, size gönderilen takip bağlantısı çalışmaya devam eder.
            </p>
          </main>
        </body>
      </html>
    );
  }

  // Yayın öncesi kilit (Shopify password page) — çerez yoksa yalnız kilit ekranı
  const locked = payload.password_protected && !payload.is_preview
    && !(await cookies()).get("vitrin_kilit");
  if (locked) {
    return (
      <html lang="tr"
        className={`${inter.variable} h-full antialiased`}
        style={{
          "--c-primary": theme.colors.primary,
          "--c-bg": theme.colors.bg,
        } as React.CSSProperties}>
        <body className="min-h-full">
          <LockScreen storeName={store_name} />
        </body>
      </html>
    );
  }

  return (
    <html
      lang="tr"
      data-reveal={theme.animations.reveal ? "1" : "0"}
      data-hover-zoom={theme.animations.hover_zoom ? "1" : "0"}
      className={`${inter.variable} ${poppins.variable} ${playfair.variable} ${dmSans.variable} h-full antialiased`}
      style={
        {
          "--c-primary": theme.colors.primary,
          "--c-accent": theme.colors.accent,
          "--c-bg": theme.colors.bg,
          "--font-active": fontFamily,
        } as React.CSSProperties
      }
    >
      <body className="min-h-full flex flex-col text-zinc-900" style={{ background: "var(--c-bg)" }}>
        {custom_code?.css && <style dangerouslySetInnerHTML={{ __html: custom_code.css }} />}
        {custom_code?.head_html && <CustomCode html={custom_code.head_html} />}
        <CartProvider>
          <Suspense><CouponFromUrl /></Suspense>
          <Pixels meta={payloadPixels?.meta} ga4={payloadPixels?.ga4} tiktok={payloadPixels?.tiktok} />
          {/* Meta Pixel temel kodu SSR ile basılır — Meta'nın "piksel saptandı"
              denetleyicisi JS çalıştırmadan kaynak HTML'e bakar; client-side
              enjeksiyonu göremez. init+PageView burada, route değişimleri Pixels'ta. */}
          {payloadPixels?.meta && (
            <>
              <script dangerouslySetInnerHTML={{ __html: `
                !function(f,b,e,v,n,t,s)
                {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
                n.callMethod.apply(n,arguments):n.queue.push(arguments)};
                if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
                n.queue=[];t=b.createElement(e);t.async=!0;
                t.src=v;s=b.getElementsByTagName(e)[0];
                s.parentNode.insertBefore(t,s)}(window, document,'script',
                'https://connect.facebook.net/en_US/fbevents.js');
                fbq('init', '${payloadPixels.meta.replace(/[^0-9]/g, "")}');
                fbq('track', 'PageView');
              ` }} />
              <noscript>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img height="1" width="1" style={{ display: "none" }} alt=""
                  src={`https://www.facebook.com/tr?id=${payloadPixels.meta.replace(/[^0-9]/g, "")}&ev=PageView&noscript=1`} />
              </noscript>
            </>
          )}
          {theme.announcement.enabled && (
            <AnnouncementBar text={theme.announcement.text} url={theme.announcement.url} />
          )}
          <Header
            siteName={store_name}
            logoUrl={theme.logo_url}
            logoWidth={theme.logo_width ?? 120}
            cartDrawer={theme.animations.cart_drawer}
            collections={navCollections.map((c) => ({ slug: c.slug, title: c.title }))}
            navLinks={theme.nav_links ?? []}
          />
          {theme.animations.cart_drawer && (
            <CartDrawer freeShippingOver={payload.settings?.free_shipping_over} />
          )}
          <main className="flex-1">{children}</main>
          <footer className="border-t border-zinc-200 bg-white mt-12">
            <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-zinc-500 space-y-4">
              <div className="max-w-sm">
                <div className="text-xs font-semibold text-zinc-700 mb-1.5">
                  {theme.texts?.newsletter_title || "📮 Kampanyalardan haberdar olun"}
                </div>
                <NewsletterForm />
              </div>
              {theme.footer.about && (
                <p className="max-w-lg text-xs leading-relaxed">{theme.footer.about}</p>
              )}
              <div className="flex flex-wrap gap-x-6 gap-y-2 items-center">
                <span>© {year} {store_name}</span>
                <a href="/gizlilik" className="hover:text-zinc-800">Gizlilik ve KVKK</a>
                <a href="/mesafeli-satis" className="hover:text-zinc-800">Mesafeli Satış Sözleşmesi</a>
                <a href="/iade" className="hover:text-zinc-800">İade ve Değişim</a>
                {payload.has_blog && <a href="/blog" className="hover:text-zinc-800">Blog</a>}
                {pages.map((pg) => (
                  <a key={pg.slug} href={`/sayfa/${pg.slug}`} className="hover:text-zinc-800">
                    {pg.title}
                  </a>
                ))}
                {instagram && (
                  <a href={`https://instagram.com/${instagram}`} target="_blank" rel="noopener noreferrer"
                    className="hover:text-zinc-800">
                    Instagram: @{instagram}
                  </a>
                )}
                {contact.email && (
                  <a href={`mailto:${contact.email}`} className="hover:text-zinc-800">{contact.email}</a>
                )}
              </div>
            </div>
          </footer>
          {theme.whatsapp?.enabled && theme.whatsapp.number && (
            <WhatsAppButton number={theme.whatsapp.number} message={theme.whatsapp.message} />
          )}
          {payload.support?.enabled !== false && (
            <SupportChat faq={payload.support?.faq ?? []}
              magaza={payload.store_name}
              whatsappVisible={!!(theme.whatsapp?.enabled && theme.whatsapp.number)} />
          )}
          {custom_code?.body_html && <CustomCode html={custom_code.body_html} />}
          <CopyGuard />
          {/* Canlı görünüm ping'i — panel anlık ziyaretçi/sepet sayar */}
          {!payload.is_preview && <Presence />}
          {payload.is_preview && <PreviewBridge />}
        </CartProvider>
      </body>
    </html>
  );
}

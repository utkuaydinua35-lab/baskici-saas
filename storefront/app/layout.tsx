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

export async function generateMetadata(): Promise<Metadata> {
  const { store_name, theme } = await getThemePayload();
  return {
    metadataBase: new URL(SITE_URL),
    title: {
      default: `${store_name} — Telefon Kılıfları`,
      template: `%s | ${store_name}`,
    },
    description:
      "Özel tasarım baskılı telefon kılıfları. Yüzlerce model için kişiye özel üretim, hızlı kargo.",
    icons: theme.favicon_url ? { icon: theme.favicon_url } : undefined,
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
          <Pixels meta={payloadPixels?.meta} ga4={payloadPixels?.ga4} tiktok={payloadPixels?.tiktok} />
          {theme.announcement.enabled && (
            <AnnouncementBar text={theme.announcement.text} url={theme.announcement.url} />
          )}
          <Header
            siteName={store_name}
            logoUrl={theme.logo_url}
            cartDrawer={theme.animations.cart_drawer}
            collections={navCollections.map((c) => ({ slug: c.slug, title: c.title }))}
          />
          {theme.animations.cart_drawer && <CartDrawer />}
          <main className="flex-1">{children}</main>
          <footer className="border-t border-zinc-200 bg-white mt-12">
            <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-zinc-500 space-y-4">
              <div className="max-w-sm">
                <div className="text-xs font-semibold text-zinc-700 mb-1.5">
                  📮 Kampanyalardan haberdar olun
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
          {custom_code?.body_html && <CustomCode html={custom_code.body_html} />}
        </CartProvider>
      </body>
    </html>
  );
}

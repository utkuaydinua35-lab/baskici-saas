import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { CartProvider } from "@/lib/cart";
import Header from "@/components/Header";

const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter" });

const SITE_NAME = process.env.SITE_NAME || "Bernz";
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3001";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — Telefon Kılıfları`,
    template: `%s | ${SITE_NAME}`,
  },
  description:
    "Özel tasarım baskılı telefon kılıfları. Yüzlerce model için kişiye özel üretim, hızlı kargo.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900">
        <CartProvider>
          <Header siteName={SITE_NAME} />
          <main className="flex-1">{children}</main>
          <footer className="border-t border-zinc-200 bg-white mt-12">
            <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-zinc-500 flex flex-wrap gap-x-6 gap-y-2">
              <span>© {new Date().getFullYear()} {SITE_NAME}</span>
              <a href="/gizlilik" className="hover:text-zinc-800">Gizlilik ve KVKK</a>
              <a href="/mesafeli-satis" className="hover:text-zinc-800">Mesafeli Satış Sözleşmesi</a>
              <a href="/iade" className="hover:text-zinc-800">İade ve Değişim</a>
            </div>
          </footer>
        </CartProvider>
      </body>
    </html>
  );
}

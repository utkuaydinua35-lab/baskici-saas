"use client";

// Üst menü — koleksiyon dropdown'u (desktop, hover'da kayar), mobil hamburger
// (soldan kayan menü), tema logosu + sepet (drawer/sayfa).
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart";

interface NavCollection {
  slug: string;
  title: string;
}

export default function Header({
  siteName,
  logoUrl,
  cartDrawer,
  collections = [],
}: {
  siteName: string;
  logoUrl?: string | null;
  cartDrawer?: boolean;
  collections?: NavCollection[];
}) {
  const { count, setDrawerOpen } = useCart();
  const [mobileOpen, setMobileOpen] = useState(false);
  const pathname = usePathname();

  // Route değişince mobil menüyü kapat
  useEffect(() => setMobileOpen(false), [pathname]);
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const cartInner = (
    <>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M6 7h12l-1.2 11.1a2 2 0 0 1-2 1.9H9.2a2 2 0 0 1-2-1.9L6 7Z" />
        <path d="M9 7V6a3 3 0 0 1 6 0v1" />
      </svg>
      Sepet
      {count > 0 && (
        <span
          className="absolute -top-2 -right-3 text-white text-[10px] rounded-full min-w-4 h-4 px-1 flex items-center justify-center"
          style={{ background: "var(--c-primary)" }}
        >
          {count}
        </span>
      )}
    </>
  );

  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur border-b border-zinc-200">
      <div className="mx-auto max-w-6xl px-4 h-14 flex items-center gap-5">
        {/* Mobil hamburger */}
        <button onClick={() => setMobileOpen(true)} aria-label="Menü"
          className="sm:hidden -ml-1 p-1 text-zinc-700">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        <Link href="/" className="font-bold text-lg tracking-tight flex items-center gap-2">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUrl} alt={siteName} className="h-8 w-auto max-w-[140px] object-contain" />
          ) : (
            siteName
          )}
        </Link>

        {/* Desktop nav */}
        <nav className="hidden sm:flex items-center gap-4 text-sm text-zinc-600">
          <Link href="/urunler" className="hover:text-zinc-900 py-4">Ürünler</Link>
          {collections.length > 0 && (
            <div className="relative group">
              <button className="hover:text-zinc-900 py-4 flex items-center gap-1">
                Koleksiyonlar
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" className="group-hover:rotate-180 transition-transform">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {/* Hover'da kayarak açılan dropdown */}
              <div className="absolute left-0 top-full pt-1 opacity-0 -translate-y-1 pointer-events-none
                group-hover:opacity-100 group-hover:translate-y-0 group-hover:pointer-events-auto
                transition-all duration-200">
                <div className="w-56 bg-white border border-zinc-200 rounded-2xl shadow-lg py-2">
                  {collections.map((c) => (
                    <Link key={c.slug} href={`/koleksiyon/${c.slug}`}
                      className="block px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50">
                      {c.title}
                    </Link>
                  ))}
                  <div className="border-t border-zinc-100 mt-1 pt-1">
                    <Link href="/urunler"
                      className="block px-4 py-2 text-xs text-zinc-400 hover:text-zinc-700">
                      Tüm ürünler →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}
        </nav>

        {cartDrawer ? (
          <button onClick={() => setDrawerOpen(true)}
            className="ml-auto relative inline-flex items-center gap-1.5 text-sm font-medium hover:text-zinc-900"
            aria-label="Sepeti aç">
            {cartInner}
          </button>
        ) : (
          <Link href="/sepet"
            className="ml-auto relative inline-flex items-center gap-1.5 text-sm font-medium hover:text-zinc-900"
            aria-label="Sepet">
            {cartInner}
          </Link>
        )}
      </div>

      {/* Mobil menü — soldan kayar */}
      <div
        onClick={() => setMobileOpen(false)}
        className={`sm:hidden fixed inset-0 z-50 bg-black/40 transition-opacity duration-300 ${
          mobileOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />
      <aside
        className={`sm:hidden fixed top-0 left-0 z-50 h-full w-72 bg-white shadow-2xl flex flex-col
          transition-transform duration-300 ease-out ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-hidden={!mobileOpen}
      >
        <div className="flex items-center justify-between px-4 h-14 border-b border-zinc-200">
          <span className="font-semibold">{siteName}</span>
          <button onClick={() => setMobileOpen(false)} aria-label="Kapat"
            className="text-zinc-400 hover:text-zinc-900 text-xl leading-none">×</button>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          <Link href="/urunler" className="block px-5 py-2.5 text-sm font-medium">Tüm Ürünler</Link>
          {collections.length > 0 && (
            <>
              <div className="px-5 pt-3 pb-1 text-[11px] uppercase tracking-wide text-zinc-400">
                Koleksiyonlar
              </div>
              {collections.map((c) => (
                <Link key={c.slug} href={`/koleksiyon/${c.slug}`}
                  className="block px-5 py-2.5 text-sm text-zinc-600">
                  {c.title}
                </Link>
              ))}
            </>
          )}
          <div className="px-5 pt-4 pb-1 text-[11px] uppercase tracking-wide text-zinc-400">
            Yardım
          </div>
          <Link href="/iade" className="block px-5 py-2.5 text-sm text-zinc-600">İade ve Değişim</Link>
          <Link href="/gizlilik" className="block px-5 py-2.5 text-sm text-zinc-600">Gizlilik ve KVKK</Link>
        </nav>
      </aside>
    </header>
  );
}

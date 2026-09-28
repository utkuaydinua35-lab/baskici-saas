"use client";

// Üst menü — koleksiyon dropdown'u (desktop, hover'da kayar), mobil hamburger
// (soldan kayan menü), tema logosu + sepet (drawer/sayfa).
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/format";

interface NavCollection {
  slug: string;
  title: string;
}

// Menüdeki açılır koleksiyon listesi — panelden elle seçilen koleksiyonlar.
// Çok öğede mega-menü gibi çok sütuna yayılır.
function CollectionsDropdown({ label, items }: { label: string; items: NavCollection[] }) {
  if (items.length === 0) return null;
  const cols = items.length > 12 ? 3 : items.length > 6 ? 2 : 1;
  return (
    <div className="relative group">
      <button className="hover:text-zinc-900 py-2 flex items-center gap-1 whitespace-nowrap">
        {label}
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" className="group-hover:rotate-180 transition-transform">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      <div className="absolute left-1/2 -translate-x-1/2 top-full pt-1 opacity-0 -translate-y-1 pointer-events-none
        group-hover:opacity-100 group-hover:!translate-y-0 group-hover:pointer-events-auto
        transition-all duration-200 z-50">
        <div className={`bg-white border border-zinc-200 rounded-2xl shadow-lg py-2 px-1 grid gap-x-2 ${
          cols === 3 ? "grid-cols-3 w-[40rem]" : cols === 2 ? "grid-cols-2 w-[28rem]" : "w-56"}`}>
          {items.map((c) => (
            <Link key={c.slug} href={`/koleksiyon/${c.slug}`}
              className="block px-4 py-2 text-sm text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50 rounded-lg whitespace-nowrap">
              {c.title}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

// Menünün kaydırmada davranışı. sm = masaüstü kırılımı (640px). "relative"
// kalır: arama kutusu ve açılır menüler header'a göre konumlanıyor.
const SABIT_SINIFI: Record<string, string> = {
  hep: "sticky top-0",
  mobil: "sticky top-0 sm:relative",
  masaustu: "relative sm:sticky sm:top-0",
  yok: "relative",
};

export default function Header({
  siteName,
  logoUrl,
  logoWidth = 120,
  logoWidthMobile = null,
  sabit = "hep",
  cartDrawer,
  collections = [],
  navLinks = [],
  layout = "left",
  ustNot = "",
  ustLinkMetin = "",
  ustLinkUrl = "",
}: {
  // left: logo solda, menü yanında | center: logo ortada, menü altında |
  // vitrin: logo ortada, altında koyu "Koleksiyonlar" + geniş arama (Füzyon)
  layout?: "left" | "center" | "vitrin";
  // vitrin düzeninde logonun solundaki küçük yazı ve sağdaki yazı bağlantısı
  ustNot?: string;
  ustLinkMetin?: string;
  ustLinkUrl?: string;
  siteName: string;
  logoUrl?: string | null;
  logoWidth?: number;
  // Mobil logo genişliği; null = masaüstüyle aynı (ekrana sığdırılır)
  logoWidthMobile?: number | null;
  // Sayfa kayarken menü görünür kalsın mı: hep | mobil | masaustu | yok
  sabit?: "hep" | "mobil" | "masaustu" | "yok";
  cartDrawer?: boolean;
  collections?: NavCollection[];
  navLinks?: { label: string; url?: string; type?: string; slugs?: string[] }[];
}) {
  const { count, setDrawerOpen } = useCart();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [bump, setBump] = useState(false);
  useEffect(() => setMounted(true), []);
  const pathname = usePathname();

  // Sepete ürün eklenince rozet zıplasın
  useEffect(() => {
    if (count === 0) return;
    setBump(true);
    const t = setTimeout(() => setBump(false), 400);
    return () => clearTimeout(t);
  }, [count]);

  // Route değişince mobil menüyü kapat
  useEffect(() => setMobileOpen(false), [pathname]);
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  // Otomatik eklenen linkler menüde zaten varsa tekrarlanmasın (mükerrer
  // "Favorilerim" şikâyeti) — mağaza sahibi menüsüne eklediyse otomatik gizlenir.
  const hasLinkTo = (path: string) => navLinks.some((l) => l.url === path);
  const hasCollectionsMenu = navLinks.some((l) => l.type === "collections");
  // Otomatik koleksiyon listesi: menüde tek tek linki verilenler de elenir
  const autoCollections = collections.filter(
    (c) => !hasLinkTo(`/koleksiyon/${c.slug}`),
  );

  const center = layout === "center";
  // Ortalı düzende etkin sayfa siyah hap olarak işaretlenir
  const aktif = (url?: string) =>
    !!url && !url.startsWith("http") &&
    (url === "/" ? pathname === "/" : pathname === url || pathname.startsWith(`${url}/`));
  const navLinkCls = (url?: string) => center
    ? `px-3 py-1.5 rounded-full whitespace-nowrap transition ${
        aktif(url) ? "bg-zinc-900 text-white" : "hover:text-zinc-900"}`
    : "hover:text-zinc-900 py-2 whitespace-nowrap";

  const cartInner = (
    <>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M6 7h12l-1.2 11.1a2 2 0 0 1-2 1.9H9.2a2 2 0 0 1-2-1.9L6 7Z" />
        <path d="M9 7V6a3 3 0 0 1 6 0v1" />
      </svg>
      {!center && <span className="hidden sm:inline">Sepet</span>}
      {count > 0 && (
        <span
          className={`absolute -top-2 -right-3 text-white text-[10px] rounded-full min-w-4 h-4 px-1 flex items-center justify-center transition-transform duration-300 ${
            bump ? "scale-150" : "scale-100"}`}
          style={{ background: "var(--c-primary)" }}
        >
          {count}
        </span>
      )}
    </>
  );

  const hamburger = (
    <button onClick={() => setMobileOpen(true)} aria-label="Menü"
      className="sm:hidden -ml-1 p-1 text-zinc-700">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
      </svg>
    </button>
  );

  const logo = (
    <Link href="/" className={`font-bold tracking-tight flex items-center gap-2 ${
      center ? "text-xl sm:text-2xl justify-center" : "text-lg"}`}>
      {logoUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        // Mobil ve masaüstü genişliği ayrı: CSS değişkeni + sm: kırılımı
        <img src={logoUrl} alt={siteName}
          className="h-auto object-contain w-[var(--logo-m)] sm:w-[var(--logo-d)]"
          style={{
            "--logo-d": `${logoWidth}px`,
            "--logo-m": `${logoWidthMobile ?? logoWidth}px`,
            maxWidth: center ? "40vw" : "45vw",
          } as React.CSSProperties} />
      ) : (
        siteName
      )}
    </Link>
  );

  // Masaüstü menü — panelden özel menü tanımlıysa o kullanılır.
  const navItems = (
    <>
      {navLinks.length > 0 ? (
        navLinks.map((l, li) => (
          l.type === "collections" ? (
            <CollectionsDropdown key={`cm-${li}`} label={l.label}
              items={(l.slugs || [])
                .map((s) => collections.find((c) => c.slug === s))
                .filter((c): c is NavCollection => !!c)} />
          ) : l.url?.startsWith("http") ? (
            // Dış adresler (örn. sipariş takip alt alan adı) yeni sekmede açılır
            <a key={`${l.label}-${l.url}`} href={l.url}
              target="_blank" rel="noopener noreferrer"
              className={navLinkCls(l.url)}>
              {l.label}
            </a>
          ) : (
            <Link key={`${l.label}-${l.url}`} href={l.url || "/"}
              className={navLinkCls(l.url)}>
              {l.label}
            </Link>
          )
        ))
      ) : (
      <Link href="/urunler" className={navLinkCls("/urunler")}>Ürünler</Link>
      )}
      {navLinks.length === 0 && collections.length > 0 && (
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
    </>
  );

  // TELEFON: ikonlar 19-20px dokunma alanına sahipti (ölçüldü) —
  // p-2/-m-2 ile alan ~36px'e çıkıyor, GÖRÜNÜM değişmiyor.
  const hesapVeSepet = (
    <>
      <FavHeaderLink />
      <Link href="/hesap" aria-label="Hesabım"
        className="p-2 -m-2 sm:p-0 sm:m-0 inline-flex items-center gap-1.5 text-sm font-medium text-zinc-600 hover:text-zinc-900">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="8" r="3.5" />
          <path d="M4.5 20c1.2-3.5 4-5.5 7.5-5.5s6.3 2 7.5 5.5" />
        </svg>
        {!center && <span className="hidden sm:inline">Hesap</span>}
      </Link>
      {cartDrawer ? (
        <button onClick={() => setDrawerOpen(true)}
          className="p-2 -m-2 sm:p-0 sm:m-0 relative inline-flex items-center gap-1.5 text-sm font-medium hover:text-zinc-900"
          aria-label="Sepeti aç">
          {cartInner}
        </button>
      ) : (
        <Link href="/sepet"
          className="p-2 -m-2 sm:p-0 sm:m-0 relative inline-flex items-center gap-1.5 text-sm font-medium hover:text-zinc-900"
          aria-label="Sepet">
          {cartInner}
        </Link>
      )}
    </>
  );

  if (layout === "vitrin") {
    const sepetDugmesi = cartDrawer ? (
      <button onClick={() => setDrawerOpen(true)} aria-label="Sepeti aç"
        className="relative inline-flex items-center gap-2 text-xs p-2 -m-2">
        {cartInner}
      </button>
    ) : (
      <Link href="/sepet" aria-label="Sepet" className="relative inline-flex items-center gap-2 text-xs p-2 -m-2">
        {cartInner}
      </Link>
    );
    return (
      <header className={`${SABIT_SINIFI[sabit] ?? SABIT_SINIFI.hep} z-40 bg-white`}>
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid grid-cols-[.6fr_auto_1fr] sm:grid-cols-[1fr_auto_1fr] items-center gap-3 h-[84px] sm:h-[104px]">
            <div className="min-w-0">
              {ustNot && (
                <Link href="/urunler" className="block text-[7px] sm:text-[10px] tracking-[.12em] sm:tracking-[.2em] leading-relaxed text-zinc-500 uppercase max-w-[70px] sm:max-w-none">
                  {ustNot}
                </Link>
              )}
            </div>
            {logo}
            <div className="flex items-center justify-end gap-4 sm:gap-6 text-zinc-800">
              <FavHeaderLink />
              {ustLinkMetin && ustLinkUrl && (
                ustLinkUrl.startsWith("http")
                  ? <a href={ustLinkUrl} target="_blank" rel="noopener noreferrer" className="hidden md:inline text-xs text-zinc-500 hover:text-zinc-900">{ustLinkMetin}</a>
                  : <Link href={ustLinkUrl} className="hidden md:inline text-xs text-zinc-500 hover:text-zinc-900">{ustLinkMetin}</Link>
              )}
              {sepetDugmesi}
            </div>
          </div>
          <div className="relative flex gap-2.5 sm:gap-5 pb-4 sm:pb-5">
            <KoleksiyonMenusu navLinks={navLinks} collections={collections} autoCollections={autoCollections}
              hasLinkTo={hasLinkTo} hasCollectionsMenu={hasCollectionsMenu} />
            <AramaCubugu />
          </div>
        </div>
      </header>
    );
  }

  return (
    // backdrop-blur YOK: sabit header'ın altından akan şeritler ve kaydırılan
    // içerik geçer; bulanıklık her karede yeniden hesaplanıp mobilde kaydırmayı
    // takıltır. Yerine neredeyse opak zemin (görünüm aynı).
    <header className={`${SABIT_SINIFI[sabit] ?? SABIT_SINIFI.hep} z-40 border-b border-zinc-200 ${center ? "" : "bg-white/[.97]"}`}
      style={center ? { background: "color-mix(in srgb, var(--c-bg) 97%, transparent)" } : undefined}>
      {center ? (
        <div className="mx-auto max-w-6xl px-4 py-2 sm:pt-5 sm:pb-3">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div className="flex items-center gap-4">
              {hamburger}
              <SearchBox ikonOnly />
            </div>
            {logo}
            <div className="flex items-center justify-end gap-4">{hesapVeSepet}</div>
          </div>
          <nav className="hidden sm:flex flex-wrap items-center justify-center gap-x-1 gap-y-1 mt-4 text-sm text-zinc-700">
            {navItems}
          </nav>
        </div>
      ) : (
        <div className="mx-auto max-w-6xl px-4 min-h-14 py-1.5 flex items-center gap-5">
          {hamburger}
          {logo}
          {/* flex-wrap + justify-center: sığmayan butonlar etiketi kırmak yerine
              ORTALANMIŞ ikinci satıra iner (Shopify header davranışı). */}
          <nav className="hidden sm:flex flex-1 flex-wrap items-center justify-center gap-x-4 gap-y-0 text-sm text-zinc-600 min-w-0">
            {navItems}
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <SearchBox />
            {hesapVeSepet}
          </div>
        </div>
      )}

      {/* Mobil menü — soldan kayar. Portal ile body'ye basılır: header'ın
          sticky z-40 stacking context'i içinde kalsa hero/sepet gibi
          katmanların altında ezilirdi. */}
      {mounted && createPortal(<>
      <div
        onClick={() => setMobileOpen(false)}
        className={`sm:hidden fixed inset-0 z-[95] bg-black/40 transition-opacity duration-300 ${
          mobileOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        }`}
      />
      <aside
        className={`sm:hidden fixed top-0 left-0 z-[96] h-full w-72 bg-white shadow-2xl flex flex-col
          transition-transform duration-300 ease-out ${mobileOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-hidden={!mobileOpen}
      >
        <div className="flex items-center justify-between px-4 h-14 border-b border-zinc-200">
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logoUrl} alt={siteName} style={{ width: Math.min(logoWidthMobile ?? logoWidth, 140) }}
              className="max-h-9 object-contain object-left" />
          ) : (
            <span className="font-semibold">{siteName}</span>
          )}
          <button onClick={() => setMobileOpen(false)} aria-label="Kapat"
            className="text-zinc-400 hover:text-zinc-900 text-xl leading-none">×</button>
        </div>
        <nav className="flex-1 overflow-y-auto py-3">
          {navLinks.map((l, li) => (
            l.type === "collections" ? (
              <div key={`m-cm-${li}`}>
                <div className="px-5 pt-3 pb-1 text-[11px] uppercase tracking-wide text-zinc-400">
                  {l.label}
                </div>
                {(l.slugs || [])
                  .map((s) => collections.find((c) => c.slug === s))
                  .filter((c): c is NavCollection => !!c)
                  .map((c) => (
                    <Link key={`m-cm-${c.slug}`} href={`/koleksiyon/${c.slug}`}
                      className="block px-5 py-2.5 text-sm text-zinc-600">
                      {c.title}
                    </Link>
                  ))}
              </div>
            ) : l.url?.startsWith("http") ? (
              <a key={`m-${l.label}-${l.url}`} href={l.url}
                target="_blank" rel="noopener noreferrer"
                className="block px-5 py-2.5 text-sm font-medium">
                {l.label}
              </a>
            ) : (
              <Link key={`m-${l.label}-${l.url}`} href={l.url || "/"}
                className="block px-5 py-2.5 text-sm font-medium">
                {l.label}
              </Link>
            )
          ))}
          {navLinks.length === 0 && (
            <Link href="/urunler" className="block px-5 py-2.5 text-sm font-medium">Tüm Ürünler</Link>
          )}
          {!hasLinkTo("/hesap") && (
            <Link href="/hesap" className="block px-5 py-2.5 text-sm font-medium">👤 Hesabım</Link>
          )}
          {!hasLinkTo("/favoriler") && (
            <Link href="/favoriler" className="block px-5 py-2.5 text-sm font-medium">❤️ Favorilerim</Link>
          )}
          {!hasCollectionsMenu && autoCollections.length > 0 && (
            <>
              <div className="px-5 pt-3 pb-1 text-[11px] uppercase tracking-wide text-zinc-400">
                Koleksiyonlar
              </div>
              {autoCollections.map((c) => (
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
      </>, document.body)}
    </header>
  );
}

interface Suggestion {
  slug: string;
  title: string;
  price: string;
  currency: string;
  cover_image: string | null;
}

// Canlı arama — ikona tıklayınca header altında tam genişlik kutu açılır,
// 250ms debounce ile öneri listesi; Enter tüm sonuçlara gider.
function SearchBox({ ikonOnly = false }: { ikonOnly?: boolean }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (open) inputRef.current?.focus();
    else { setQ(""); setResults([]); }
  }, [open]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) { setResults([]); return; }
    setLoading(true);
    const t = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(term)}`)
        .then((r) => (r.ok ? r.json() : { items: [] }))
        .then((d) => setResults(d.items || []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    setOpen(false);
    router.push(`/urunler?q=${encodeURIComponent(term)}`);
  };

  return (
    <>
      <button onClick={() => setOpen(true)} aria-label="Ara"
        className="p-2 -m-2 sm:p-0 sm:m-0 inline-flex items-center gap-1.5 text-sm font-medium text-zinc-600 hover:text-zinc-900">
        <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="11" cy="11" r="7" />
          <line x1="21" y1="21" x2="16.5" y2="16.5" />
        </svg>
        {!ikonOnly && <span className="hidden md:inline">Ara</span>}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-black/30" onClick={() => setOpen(false)} />
          <div className="absolute inset-x-0 top-full z-50 bg-white border-b border-zinc-200 shadow-lg">
            <form onSubmit={submit} className="mx-auto max-w-2xl px-4 py-3">
              <div className="flex items-center gap-2">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="1.8" className="text-zinc-400 shrink-0">
                  <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" />
                </svg>
                <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="Ürün ara…" aria-label="Ürün ara"
                  className="flex-1 py-2 text-sm outline-none bg-transparent" />
                <button type="button" onClick={() => setOpen(false)} aria-label="Kapat"
                  className="text-zinc-400 hover:text-zinc-900 text-xl leading-none px-1">×</button>
              </div>

              {q.trim().length >= 2 && (
                <div className="border-t border-zinc-100 mt-1 pt-1 pb-1 max-h-80 overflow-y-auto">
                  {results.map((r) => (
                    <Link key={r.slug} href={`/urun/${r.slug}`}
                      className="flex items-center gap-3 px-1 py-2 rounded-lg hover:bg-zinc-50">
                      <div className="w-10 h-10 rounded-lg bg-zinc-100 overflow-hidden shrink-0">
                        {r.cover_image ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={r.cover_image} alt="" className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-zinc-300">📱</div>
                        )}
                      </div>
                      <span className="flex-1 text-sm line-clamp-1">{r.title}</span>
                      <span className="text-sm font-medium whitespace-nowrap">
                        {formatPrice(r.price, r.currency)}
                      </span>
                    </Link>
                  ))}
                  {!loading && results.length === 0 && (
                    <p className="px-1 py-3 text-sm text-zinc-400">Sonuç bulunamadı.</p>
                  )}
                  {results.length > 0 && (
                    <button type="submit"
                      className="w-full text-left px-1 py-2 text-xs text-zinc-500 hover:text-zinc-900">
                      “{q.trim()}” için tüm sonuçları gör →
                    </button>
                  )}
                </div>
              )}
            </form>
          </div>
        </>
      )}
    </>
  );
}

// Favoriler linki — localStorage sayacını "fav-changed" olayıyla canlı tutar.
function FavHeaderLink() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const read = () => {
      try {
        const raw = localStorage.getItem("vitrin_favoriler");
        const list = raw ? JSON.parse(raw) : [];
        setCount(Array.isArray(list) ? list.length : 0);
      } catch { setCount(0); }
    };
    read();
    const onChange = (e: Event) =>
      setCount((e as CustomEvent<{ count: number }>).detail?.count ?? 0);
    window.addEventListener("fav-changed", onChange);
    return () => window.removeEventListener("fav-changed", onChange);
  }, []);

  return (
    <Link href="/favoriler" aria-label="Favorilerim"
      className="relative hidden sm:inline-flex items-center text-zinc-600 hover:text-zinc-900">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z" />
      </svg>
      {count > 0 && (
        <span className="absolute -top-2 -right-2.5 text-white text-[10px] rounded-full min-w-4 h-4 px-1 flex items-center justify-center"
          style={{ background: "var(--c-accent)" }}>
          {count}
        </span>
      )}
    </Link>
  );
}

// ── Vitrin düzeni (Füzyon) parçaları ────────────────────────────────────

// Koyu "Koleksiyonlar ☰" düğmesi + altında açılan menü kartı. Mobilde yalnız
// ikon görünür; kart iki boyutta da aynı (soldan kayan çekmece gerekmez).
function KoleksiyonMenusu({ navLinks, collections, autoCollections, hasLinkTo, hasCollectionsMenu }: {
  navLinks: { label: string; url?: string; type?: string; slugs?: string[] }[];
  collections: NavCollection[];
  autoCollections: NavCollection[];
  hasLinkTo: (path: string) => boolean;
  hasCollectionsMenu: boolean;
}) {
  const [acik, setAcik] = useState(false);
  const kap = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  useEffect(() => setAcik(false), [pathname]);
  useEffect(() => {
    if (!acik) return;
    const dis = (e: PointerEvent) => { if (!kap.current?.contains(e.target as Node)) setAcik(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setAcik(false); };
    document.addEventListener("pointerdown", dis);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", dis); document.removeEventListener("keydown", esc); };
  }, [acik]);

  const satir = "block py-3.5 text-[15px] text-zinc-800 border-b border-zinc-100 last:border-b-0 hover:text-zinc-500";
  const baslik = "pt-4 pb-1 text-[10px] uppercase tracking-[.14em] text-zinc-400";
  return (
    <div ref={kap} className="shrink-0">
      <button type="button" onClick={() => setAcik((a) => !a)} aria-expanded={acik} aria-label="Koleksiyonları aç"
        className="h-full flex items-center justify-between gap-3 w-[46px] sm:w-[240px] rounded-[10px] bg-zinc-900 text-white px-3 sm:px-[22px] py-3 sm:py-[15px] text-left text-sm">
        <span className="hidden sm:inline">Koleksiyonlar</span>
        <span aria-hidden className="text-xl leading-none w-5 text-center">{acik ? "×" : "☰"}</span>
      </button>
      {acik && (
        <nav aria-label="Koleksiyon menüsü"
          className="absolute left-0 top-full z-50 mt-1 w-[min(330px,92vw)] max-h-[70vh] overflow-y-auto rounded-xl border border-zinc-100 bg-white px-6 py-3 shadow-[0_15px_40px_#0002]">
          {navLinks.map((l, li) => l.type === "collections" ? (
            <div key={`v-cm-${li}`}>
              <div className={baslik}>{l.label}</div>
              {(l.slugs || []).map((s2) => collections.find((c) => c.slug === s2))
                .filter((c): c is NavCollection => !!c)
                .map((c) => <Link key={c.slug} href={`/koleksiyon/${c.slug}`} className={satir}>{c.title}</Link>)}
            </div>
          ) : l.url?.startsWith("http") ? (
            <a key={`v-${li}`} href={l.url} target="_blank" rel="noopener noreferrer" className={satir}>{l.label}</a>
          ) : (
            <Link key={`v-${li}`} href={l.url || "/"} className={satir}>{l.label}</Link>
          ))}
          {navLinks.length === 0 && <Link href="/urunler" className={satir}>Tüm ürünler</Link>}
          {!hasCollectionsMenu && autoCollections.length > 0 && (
            <>
              <div className={baslik}>Koleksiyonlar</div>
              {autoCollections.map((c) => <Link key={c.slug} href={`/koleksiyon/${c.slug}`} className={satir}>{c.title}</Link>)}
            </>
          )}
          {!hasLinkTo("/hesap") && <Link href="/hesap" className={satir}>Hesabım</Link>}
          {!hasLinkTo("/favoriler") && <Link href="/favoriler" className={satir}>Favorilerim</Link>}
        </nav>
      )}
    </div>
  );
}

// Her zaman görünen geniş arama çubuğu — yazdıkça öneri listesi (250 ms
// gecikmeli), Enter tüm sonuçlara gider.
function AramaCubugu() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Suggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [odak, setOdak] = useState(false);
  const kap = useRef<HTMLFormElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => { setQ(""); setResults([]); }, [pathname]);
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) { setResults([]); return; }
    setLoading(true);
    const t = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(term)}`)
        .then((r) => (r.ok ? r.json() : { items: [] }))
        .then((d) => setResults(d.items || []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    if (!odak) return;
    const dis = (e: PointerEvent) => { if (!kap.current?.contains(e.target as Node)) setOdak(false); };
    document.addEventListener("pointerdown", dis);
    return () => document.removeEventListener("pointerdown", dis);
  }, [odak]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    setOdak(false);
    router.push(`/urunler?q=${encodeURIComponent(term)}`);
  };
  const acik = odak && q.trim().length >= 2;
  return (
    <form ref={kap} onSubmit={submit} role="search"
      className="relative flex-1 min-w-0 flex items-center rounded-[10px] bg-zinc-100 px-2.5 sm:px-4 focus-within:outline focus-within:outline-2 focus-within:outline-zinc-500">
      <label htmlFor="vitrin-ara" className="sr-only">Ürün ara</label>
      <input id="vitrin-ara" type="search" value={q} autoComplete="off"
        onChange={(e) => { setQ(e.target.value); setOdak(true); }} onFocus={() => setOdak(true)}
        onKeyDown={(e) => { if (e.key === "Escape") setOdak(false); }}
        placeholder="Tasarım ara…"
        className="w-full min-w-0 bg-transparent py-3 sm:py-4 text-xs sm:text-sm outline-none text-zinc-800 placeholder:text-zinc-500" />
      <button type="submit" aria-label="Ara" className="shrink-0 w-8 h-9 sm:w-9 sm:h-10 grid place-items-center text-zinc-800">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5" aria-hidden>
          <circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" />
        </svg>
      </button>
      {acik && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1.5 rounded-xl border border-zinc-200 bg-white p-1.5 shadow-lg max-h-80 overflow-y-auto">
          {results.map((r) => (
            <Link key={r.slug} href={`/urun/${r.slug}`}
              className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-zinc-50">
              <div className="w-10 h-10 rounded-lg bg-zinc-100 overflow-hidden shrink-0">
                {r.cover_image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={r.cover_image} alt="" className="w-full h-full object-cover" />
                ) : null}
              </div>
              <span className="flex-1 text-sm line-clamp-1">{r.title}</span>
              <span className="text-sm font-medium whitespace-nowrap">{formatPrice(r.price, r.currency)}</span>
            </Link>
          ))}
          {!loading && results.length === 0 && <p className="px-2 py-3 text-sm text-zinc-400">Sonuç bulunamadı.</p>}
          {results.length > 0 && (
            <button type="submit" className="w-full text-left px-2 py-2 text-xs text-zinc-500 hover:text-zinc-900">
              “{q.trim()}” için tüm sonuçları gör →
            </button>
          )}
        </div>
      )}
    </form>
  );
}

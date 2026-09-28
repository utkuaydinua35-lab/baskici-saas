import Link from "next/link";
import NewsletterForm from "@/components/NewsletterForm";

// Geniş footer (tema style.footer_stil = "genis") — açık zeminde logo +
// tanıtım + bülten, "Keşfet" ve "İletişim & Destek" sütunları, altta telif,
// güvenli ödeme notu ve "Yukarı dön".
export default function GenisFooter({
  storeName,
  logoUrl,
  about,
  instagram,
  email,
  pages,
  hasBlog,
  navLinks,
  year,
  newsletterTitle,
  sslText,
}: {
  storeName: string;
  logoUrl: string | null;
  about?: string;
  instagram?: string;
  email?: string | null;
  pages: { slug: string; title: string }[];
  hasBlog: boolean;
  navLinks: { label: string; url?: string; type?: string }[];
  year: number;
  newsletterTitle?: string;
  sslText?: string;
}) {
  const kesfet = navLinks.filter((l) => l.url && l.type !== "collections").slice(0, 6);
  const link = "hover:underline underline-offset-4";
  return (
    <footer className="vitrin-footer relative bg-[#f0f0ed] text-zinc-800 mt-12">
      <div className="mx-auto max-w-6xl px-5 pt-12 sm:pt-16 pb-6">
        <div className="grid grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr] gap-x-6 gap-y-9 lg:gap-14 pb-9 sm:pb-10">
          <div className="col-span-2 lg:col-span-1">
            <Link href="/" aria-label={`${storeName} ana sayfa`} className="inline-block">
              {logoUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={logoUrl} alt={storeName} className="h-auto w-[195px] sm:w-[245px] max-w-full" />
              ) : (
                <span className="f-baslik text-3xl">{storeName}</span>
              )}
            </Link>
            {about && <p className="mt-4 text-[13px] leading-[1.8] text-zinc-500 max-w-[270px] whitespace-pre-line">{about}</p>}
            <div className="mt-5 max-w-sm">
              <div className="text-[10px] tracking-[.16em] uppercase text-zinc-500 mb-2">
                {newsletterTitle || "Kampanyalardan haberdar olun"}
              </div>
              <NewsletterForm />
            </div>
          </div>
          <div>
            <h3 className="text-[10px] tracking-[.16em] uppercase mb-5">Keşfet</h3>
            <div className="flex flex-col gap-3 text-xs sm:text-[13px]">
              {kesfet.length > 0 ? kesfet.map((l) => (
                l.url!.startsWith("http")
                  ? <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className={link}>{l.label}</a>
                  : <Link key={l.url} href={l.url!} className={link}>{l.label}</Link>
              )) : <Link href="/urunler" className={link}>Tüm ürünler</Link>}
              <Link href="/favoriler" className={link}>Favorilerim</Link>
              {hasBlog && <Link href="/blog" className={link}>Blog</Link>}
            </div>
          </div>
          <div>
            <h3 className="text-[10px] tracking-[.16em] uppercase mb-5">İletişim & Destek</h3>
            <div className="flex flex-col gap-3 text-xs sm:text-[13px]">
              {email && <a href={`mailto:${email}`} className={`${link} break-all`}>{email}</a>}
              {instagram && (
                <a href={`https://instagram.com/${instagram}`} target="_blank" rel="noopener noreferrer" className={link}>
                  Instagram
                </a>
              )}
              <Link href="/hesap" className={link}>Siparişlerim</Link>
              <Link href="/iade" className={link}>İade ve Değişim</Link>
              <Link href="/gizlilik" className={link}>Gizlilik ve KVKK</Link>
              <Link href="/mesafeli-satis" className={link}>Mesafeli Satış Sözleşmesi</Link>
              {pages.map((pg) => <Link key={pg.slug} href={`/sayfa/${pg.slug}`} className={link}>{pg.title}</Link>)}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-3 border-t border-zinc-300/60 pt-6 text-[10px] tracking-wide text-zinc-500">
          <span>© {year} {storeName}</span>
          <span className="inline-flex items-center gap-1.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-[13px] h-[13px]" aria-hidden>
              <rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" />
            </svg>
            {sslText || "256-bit SSL ile güvenli ödeme"}
          </span>
          <a href="#" className="hover:text-zinc-900">Yukarı dön ↑</a>
        </div>
      </div>
    </footer>
  );
}

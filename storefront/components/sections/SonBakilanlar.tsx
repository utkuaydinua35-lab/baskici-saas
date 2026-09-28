"use client";

// Son baktığın tasarımlar (Füzyon) — ürün sayfası (RecentlyViewed) tarayıcıya
// kaydeder, anasayfada şerit olarak gösterilir. Veri cihazda kalır; ilk kez
// gelen ziyaretçide liste boş → bölüm HİÇ görünmez. "Geçmişi temizle" siler.
import { useEffect, useState } from "react";
import Link from "next/link";
import { formatPrice } from "@/lib/format";
import { urunGorsel } from "@/lib/gorsel";
import SectionHeading from "@/components/SectionHeading";

const ANAHTAR = "vitrin_son_gezilenler";   // RecentlyViewed ile aynı

interface Bakilan { slug: string; title: string; price: string; currency: string; image: string | null }

export default function SonBakilanlar({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
}) {
  const [liste, setListe] = useState<Bakilan[]>([]);
  useEffect(() => {
    try {
      const l = JSON.parse(localStorage.getItem(ANAHTAR) || "[]");
      setListe(Array.isArray(l) ? l.filter((x) => x?.slug).slice(0, 4) : []);
    } catch { setListe([]); }
  }, []);
  if (liste.length === 0) return null;

  const temizle = () => {
    try { localStorage.removeItem(ANAHTAR); } catch { /* gizli sekme */ }
    setListe([]);
  };

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 sm:py-10">
      <div className="flex items-end justify-between gap-5">
        <div className="flex-1 min-w-0">
          <SectionHeading eyebrow={eyebrow} title={title || "Son baktığın tasarımlar"} subtitle={subtitle} />
        </div>
        <button type="button" onClick={temizle}
          className="shrink-0 mb-5 sm:mb-7 text-[10px] sm:text-[11px] text-zinc-400 underline underline-offset-4 hover:text-zinc-800">
          Geçmişi temizle
        </button>
      </div>
      <div className="serit-gizli flex gap-3 sm:gap-4 overflow-x-auto snap-x pb-2">
        {liste.map((b) => (
          <Link key={b.slug} href={`/urun/${b.slug}`}
            className="group shrink-0 snap-start w-[245px] sm:w-[280px] flex items-center gap-3 sm:gap-4 rounded-xl border border-zinc-200 p-2.5 sm:p-3 transition-[background-color,transform] duration-200 hover:bg-zinc-50 hover:-translate-y-0.5">
            <span className="w-[63px] h-[73px] sm:w-[70px] sm:h-[80px] shrink-0 rounded-md overflow-hidden bg-zinc-100">
              {b.image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={urunGorsel(b.image).src} srcSet={urunGorsel(b.image).srcSet || undefined} sizes="80px"
                  alt={b.title} loading="lazy" decoding="async" className="w-full h-full object-cover" />
              )}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] sm:text-sm line-clamp-2">{b.title}</span>
              <span className="block mt-1.5 text-[11px] sm:text-xs text-zinc-500">{formatPrice(b.price, b.currency)}</span>
            </span>
            <span aria-hidden className="text-lg text-zinc-500 transition-transform group-hover:translate-x-1">→</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

"use client";

// Büyük görsel karuseli ("Autumn Koleksiyonu" kalıbı): üstte aralıklı küçük
// üst başlık, kalın büyük başlık, gri alt metin; altında ARKASI SAYDAM büyük
// ürün görselleri — zemin sitenin rengi görünür, kart/çerçeve yok. Oklarla ya
// da kaydırarak geçilir; isteğe bağlı kendiliğinden ilerler.
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { urunGorsel } from "@/lib/gorsel";

type Oge = { gorsel: string; link?: string; etiket?: string };

export default function BuyukKarusel({ eyebrow, title, subtitle, ogeler = [], goster = "2", otoSn = 0 }: {
  eyebrow?: string; title?: string; subtitle?: string;
  ogeler?: Oge[]; goster?: "1" | "2" | "3"; otoSn?: number;
}) {
  const iz = useRef<HTMLDivElement>(null);
  const [bas, setBas] = useState(true);
  const [son, setSon] = useState(false);
  const [durdu, setDurdu] = useState(false);

  const kontrol = useCallback(() => {
    const el = iz.current;
    if (!el) return;
    setBas(el.scrollLeft < 8);
    setSon(el.scrollLeft + el.clientWidth >= el.scrollWidth - 8);
  }, []);

  const kaydir = useCallback((yon: 1 | -1) => {
    const el = iz.current;
    if (!el) return;
    const kart = el.querySelector<HTMLElement>("[data-karusel-oge]");
    const adim = kart ? kart.offsetWidth : el.clientWidth;
    // Sonda ileri: başa dön (otomatik ilerlemede döngü)
    if (yon === 1 && el.scrollLeft + el.clientWidth >= el.scrollWidth - 8) el.scrollTo({ left: 0, behavior: "smooth" });
    else el.scrollBy({ left: yon * adim, behavior: "smooth" });
  }, []);

  useEffect(() => { kontrol(); }, [kontrol, ogeler.length]);
  useEffect(() => {
    if (!otoSn || durdu || ogeler.length < 2) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const z = window.setInterval(() => kaydir(1), otoSn * 1000);
    return () => window.clearInterval(z);
  }, [otoSn, durdu, ogeler.length, kaydir]);

  if (ogeler.length === 0) return null;
  const genislik = goster === "1" ? "md:basis-full" : goster === "3" ? "md:basis-1/3" : "md:basis-1/2";

  return (
    <section className="py-12 sm:py-16"
      onMouseEnter={() => setDurdu(true)} onMouseLeave={() => setDurdu(false)}>
      {(eyebrow || title || subtitle) && (
        <div className="mx-auto max-w-4xl px-4 text-center mb-6 sm:mb-10">
          {eyebrow && (
            <div className="text-[11px] sm:text-[13px] font-bold uppercase tracking-[0.3em] mb-2 sm:mb-3">{eyebrow}</div>
          )}
          {title && (
            <h2 className="text-3xl sm:text-5xl md:text-6xl font-extrabold tracking-tight leading-[1.05]">{title}</h2>
          )}
          {subtitle && <p className="mt-3 sm:mt-4 text-base sm:text-xl text-zinc-500">{subtitle}</p>}
        </div>
      )}
      <div className="relative">
        <div ref={iz} onScroll={kontrol}
          className="serit-gizli flex overflow-x-auto snap-x snap-mandatory scroll-smooth">
          {ogeler.map((o, i) => {
            const gorsel = (
              // eslint-disable-next-line @next/next/no-img-element
              // Saydamlık korunur (yüklemede PNG kalır, küçük boyutlar alfalı WebP)
              <img src={urunGorsel(o.gorsel).src} srcSet={urunGorsel(o.gorsel).srcSet || undefined}
                sizes={goster === "1" ? "100vw" : goster === "3" ? "(min-width: 768px) 33vw, 86vw" : "(min-width: 768px) 50vw, 86vw"}
                alt={o.etiket || title || ""} loading={i < 2 ? "eager" : "lazy"} decoding="async"
                className="mx-auto block h-[min(72vh,820px)] min-h-[340px] w-auto max-w-full object-contain select-none"
                draggable={false} />
            );
            return (
              <div key={i} data-karusel-oge className={`snap-center shrink-0 basis-[86%] ${genislik} px-2 sm:px-6`}>
                {o.link ? <Link href={o.link} aria-label={o.etiket || "Ürüne git"}>{gorsel}</Link> : gorsel}
                {o.etiket && <div className="mt-3 text-center text-sm font-medium">{o.etiket}</div>}
              </div>
            );
          })}
        </div>
        {ogeler.length > 1 && (
          <>
            <button type="button" onClick={() => kaydir(-1)} aria-label="Önceki" disabled={bas}
              className="absolute left-1 sm:left-3 top-1/2 -translate-y-1/2 grid h-11 w-11 place-items-center text-3xl leading-none disabled:opacity-20 transition-opacity">
              ‹
            </button>
            <button type="button" onClick={() => kaydir(1)} aria-label="Sonraki" disabled={son && !otoSn}
              className="absolute right-1 sm:right-3 top-1/2 -translate-y-1/2 grid h-11 w-11 place-items-center text-3xl leading-none disabled:opacity-20 transition-opacity">
              ›
            </button>
          </>
        )}
      </div>
    </section>
  );
}

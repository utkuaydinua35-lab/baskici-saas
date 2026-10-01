"use client";

// Oklu yatay şerit — ürün, hikâye kartı vb. için ortak. Çocuklar sunucuda
// render edilir; burası yalnız kaydırma davranışını ekler.
//  • Oklar yalnız taşma varken görünür (masaüstü); dokunmatikte parmakla kayar.
//  • autoplaySec > 0 ise bir kart ilerler, sona gelince başa döner.
//
// DOKUNMATİK TUZAKLARI (iPhone'da "dokununca kilitleniyor, duruyor kalıyor"):
//  1. Fareyle üstüne gelince durdurma onMouseEnter ile yapılıyordu. iOS
//     dokunuşta sahte mouseenter üretir ama mouseleave GÖNDERMEZ → tek
//     dokunuştan sonra otomatik ilerleme KALICI olarak duruyordu. Artık
//     durdurma yalnız pointerType === "mouse" iken.
//  2. Otomatik yumuşak kaydırma sürerken parmak değince tarayıcı ikisini
//     çekiştiriyordu. Dokunuşta süren animasyon kesilir, son etkileşimden
//     ETKILESIM_BEKLE ms geçmeden otomatik ilerleme çalışmaz.
//  3. Ok görünürlüğü her kaydırma karesinde yeni nesneyle state'e yazılıp
//     bileşeni baştan çizdiriyordu. Artık kare başına bir ölçüm (rAF) ve
//     yalnız DEĞİŞİNCE güncelleme.
import { hareketSorgusu } from "@/lib/hareket";
import { useCallback, useEffect, useRef, useState } from "react";

const ETKILESIM_BEKLE = 5000;

export default function Carousel({
  children,
  autoplaySec = 0,
  ariaLabel,
}: {
  children: React.ReactNode;
  autoplaySec?: number;
  ariaLabel?: string;
}) {
  const track = useRef<HTMLDivElement>(null);
  const [edges, setEdges] = useState({ start: true, end: true });
  const fareUstunde = useRef(false);
  const sonEtkilesim = useRef(0);
  const olcumKaresi = useRef<number | null>(null);

  const measure = useCallback(() => {
    if (olcumKaresi.current != null) return;
    olcumKaresi.current = requestAnimationFrame(() => {
      olcumKaresi.current = null;
      const el = track.current;
      if (!el) return;
      const start = el.scrollLeft <= 4;
      const end = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4;
      setEdges((e) => (e.start === start && e.end === end ? e : { start, end }));
    });
  }, []);

  // Bir adım = ilk kartın genişliği + boşluk (yoksa görünür alanın %80'i)
  const step = useCallback(() => {
    const el = track.current;
    if (!el) return 0;
    const first = el.firstElementChild as HTMLElement | null;
    const gap = parseFloat(getComputedStyle(el).columnGap || "0") || 0;
    return first ? first.offsetWidth + gap : el.clientWidth * 0.8;
  }, []);

  const go = useCallback((dir: 1 | -1) => {
    sonEtkilesim.current = Date.now();
    track.current?.scrollBy({ left: dir * step(), behavior: "smooth" });
  }, [step]);

  useEffect(() => {
    measure();
    const el = track.current;
    if (!el) return;
    el.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      el.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
      if (olcumKaresi.current != null) cancelAnimationFrame(olcumKaresi.current);
    };
  }, [measure]);

  useEffect(() => {
    if (!autoplaySec) return;
    if (hareketSorgusu().matches) return;
    const t = setInterval(() => {
      const el = track.current;
      if (!el || fareUstunde.current || document.hidden) return;
      if (Date.now() - sonEtkilesim.current < ETKILESIM_BEKLE) return;
      // Ekranda değilse boşuna kaydırma (pil, kaydırma çekişmesi)
      const r = el.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight) return;
      const sonda = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4;
      el.scrollTo({ left: sonda ? 0 : el.scrollLeft + step(), behavior: "smooth" });
    }, autoplaySec * 1000);
    return () => clearInterval(t);
  }, [autoplaySec, step]);

  // Dokunma/kalem: süren otomatik animasyonu kes, bir süre otomatiği beklet
  const dokundu = () => {
    sonEtkilesim.current = Date.now();
    const el = track.current;
    if (el) el.scrollTo({ left: el.scrollLeft, behavior: "instant" as ScrollBehavior });
  };

  return (
    <div className="relative" aria-label={ariaLabel} role={ariaLabel ? "region" : undefined}
      onPointerEnter={(e) => { if (e.pointerType === "mouse") fareUstunde.current = true; }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") fareUstunde.current = false; }}
      onPointerDown={(e) => { if (e.pointerType !== "mouse") dokundu(); }}
      onTouchEnd={() => { sonEtkilesim.current = Date.now(); }}
      onWheel={() => { sonEtkilesim.current = Date.now(); }}>
      <div ref={track}
        className="serit-gizli flex gap-4 overflow-x-auto snap-x snap-mandatory overscroll-x-contain pb-1">
        {children}
      </div>
      {!edges.start && (
        <button onClick={() => go(-1)} aria-label="Önceki"
          className="hidden sm:grid absolute left-0 top-1/2 -translate-x-1/3 -translate-y-1/2 z-10
            w-10 h-10 place-items-center rounded-full bg-white shadow-md border border-zinc-200
            text-zinc-800 hover:scale-105 transition">
          ‹
        </button>
      )}
      {!edges.end && (
        <button onClick={() => go(1)} aria-label="Sonraki"
          className="hidden sm:grid absolute right-0 top-1/2 translate-x-1/3 -translate-y-1/2 z-10
            w-10 h-10 place-items-center rounded-full bg-white shadow-md border border-zinc-200
            text-zinc-800 hover:scale-105 transition">
          ›
        </button>
      )}
    </div>
  );
}

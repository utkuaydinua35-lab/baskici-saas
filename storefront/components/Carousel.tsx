"use client";

// Oklu yatay şerit — ürün, hikâye kartı vb. için ortak. Çocuklar sunucuda
// render edilir; burası yalnız kaydırma davranışını ekler.
//  • Oklar yalnız taşma varken görünür (masaüstü); dokunmatikte parmakla kayar.
//  • autoplaySec > 0 ise bir kart ilerler, sona gelince başa döner. Üzerine
//    gelince / dokununca durur; hareket azaltma tercihinde hiç çalışmaz.
import { useCallback, useEffect, useRef, useState } from "react";

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
  const paused = useRef(false);

  const measure = useCallback(() => {
    const el = track.current;
    if (!el) return;
    setEdges({
      start: el.scrollLeft <= 4,
      end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 4,
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
    };
  }, [measure]);

  useEffect(() => {
    if (!autoplaySec) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => {
      const el = track.current;
      if (!el || paused.current || document.hidden) return;
      const sonda = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4;
      el.scrollTo({ left: sonda ? 0 : el.scrollLeft + step(), behavior: "smooth" });
    }, autoplaySec * 1000);
    return () => clearInterval(t);
  }, [autoplaySec, step]);

  const dur = (v: boolean) => () => { paused.current = v; };

  return (
    <div className="relative" aria-label={ariaLabel} role={ariaLabel ? "region" : undefined}
      onMouseEnter={dur(true)} onMouseLeave={dur(false)}
      onTouchStart={dur(true)} onTouchEnd={dur(false)}>
      <div ref={track}
        className="serit-gizli flex gap-4 overflow-x-auto snap-x snap-mandatory scroll-smooth pb-1">
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
